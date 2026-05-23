from __future__ import annotations

import asyncio
import json
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from api.adapters.http import HttpAdapter
from api.db import SessionLocal, get_db, init_db
from api.models import CaseResult, Run, Suite
from api.runner import _get_git_sha, run_eval
from api.schemas.api import (
    CaseComparison,
    CaseResultResponse,
    CloneSuiteRequest,
    RunComparison,
    RunDetail,
    RunStartRequest,
    RunStartResponse,
    RunSummary,
    RubricContent,
    RubricUpdate,
    ScoreDelta,
    SuiteCreate,
    SuiteResponse,
)
from api.schemas.dataset import load_dataset
from api.schemas.rubric import load_rubric, load_rubric_from_string


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="RubricLab API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


# ── Suites ────────────────────────────────────────────────────────────────────


@app.get("/suites", response_model=list[SuiteResponse])
def list_suites(db: Session = Depends(get_db)):
    return db.query(Suite).order_by(Suite.created_at.desc()).all()


@app.post("/suites", response_model=SuiteResponse, status_code=201)
def create_suite(body: SuiteCreate, db: Session = Depends(get_db)):
    suite = Suite(
        id=str(uuid.uuid4()),
        name=body.name,
        rubric_path=body.rubric_path,
        dataset_path=body.dataset_path,
    )
    db.add(suite)
    db.commit()
    db.refresh(suite)
    return suite


@app.get("/suites/{suite_id}", response_model=SuiteResponse)
def get_suite(suite_id: str, db: Session = Depends(get_db)):
    suite = db.get(Suite, suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="Suite not found")
    return suite


@app.get("/suites/{suite_id}/rubric", response_model=RubricContent)
def get_rubric(suite_id: str, db: Session = Depends(get_db)):
    suite = db.get(Suite, suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="Suite not found")
    try:
        content = Path(suite.rubric_path).read_text(encoding="utf-8")
    except OSError:
        raise HTTPException(status_code=404, detail="Rubric file not found")
    return RubricContent(content=content, path=suite.rubric_path)


@app.put("/suites/{suite_id}/rubric", response_model=RubricContent)
def update_rubric(suite_id: str, body: RubricUpdate, db: Session = Depends(get_db)):
    suite = db.get(Suite, suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="Suite not found")
    try:
        load_rubric_from_string(body.content)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    Path(suite.rubric_path).write_text(body.content, encoding="utf-8")
    return RubricContent(content=body.content, path=suite.rubric_path)


@app.post("/suites/{suite_id}/clone", response_model=SuiteResponse, status_code=201)
def clone_suite(suite_id: str, body: CloneSuiteRequest, db: Session = Depends(get_db)):
    suite = db.get(Suite, suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="Suite not found")
    rubric_path = Path(suite.rubric_path)
    safe_name = body.name.lower().replace(" ", "_")
    new_rubric_path = rubric_path.with_name(
        f"{rubric_path.stem}_{safe_name}{rubric_path.suffix}"
    )
    shutil.copy2(rubric_path, new_rubric_path)
    new_suite = Suite(
        id=str(uuid.uuid4()),
        name=body.name,
        rubric_path=str(new_rubric_path),
        dataset_path=suite.dataset_path,
    )
    db.add(new_suite)
    db.commit()
    db.refresh(new_suite)
    return new_suite


# ── Runs ──────────────────────────────────────────────────────────────────────


async def _run_background(
    run_id: str,
    suite_id: str,
    rubric,
    dataset,
    adapter,
    agent_version: str,
) -> None:
    db = SessionLocal()
    try:
        suite = db.get(Suite, suite_id)
        await asyncio.to_thread(
            run_eval, suite, rubric, dataset, adapter, db, agent_version,
            None, None, run_id,
        )
    finally:
        db.close()


@app.post("/suites/{suite_id}/runs", response_model=RunStartResponse, status_code=202)
def start_run(
    suite_id: str,
    body: RunStartRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    suite = db.get(Suite, suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="Suite not found")
    try:
        rubric = load_rubric(suite.rubric_path)
        dataset = load_dataset(suite.dataset_path)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    adapter = HttpAdapter(url=body.agent_url)

    run = Run(
        id=str(uuid.uuid4()),
        suite_id=suite_id,
        status="pending",
        git_sha=_get_git_sha(),
        agent_version=body.agent_version,
        total_cases=len(dataset),
        passed_cases=0,
    )
    db.add(run)
    db.commit()

    background_tasks.add_task(
        _run_background, run.id, suite_id, rubric, dataset, adapter, body.agent_version
    )
    return RunStartResponse(run_id=run.id, status="pending")


@app.get("/runs/compare", response_model=RunComparison)
def compare_runs(a: str, b: str, db: Session = Depends(get_db)):
    run_a = db.get(Run, a)
    run_b = db.get(Run, b)
    if not run_a or not run_b:
        raise HTTPException(status_code=404, detail="Run not found")

    cases_a = {
        c.case_id: c
        for c in db.query(CaseResult).filter(CaseResult.run_id == a).all()
    }
    cases_b = {
        c.case_id: c
        for c in db.query(CaseResult).filter(CaseResult.run_id == b).all()
    }

    all_case_ids = sorted(set(cases_a.keys()) | set(cases_b.keys()))
    comparisons: list[CaseComparison] = []
    for case_id in all_case_ids:
        ca = cases_a.get(case_id)
        cb = cases_b.get(case_id)
        a_passed = ca.passed if ca else None
        b_passed = cb.passed if cb else None
        flipped = a_passed is not None and b_passed is not None and a_passed != b_passed

        a_scores: dict = (
            json.loads(ca.rubric_scores)
            if isinstance(ca.rubric_scores, str)
            else ca.rubric_scores
        ) if ca else {}
        b_scores: dict = (
            json.loads(cb.rubric_scores)
            if isinstance(cb.rubric_scores, str)
            else cb.rubric_scores
        ) if cb else {}

        score_deltas: dict[str, ScoreDelta] = {}
        for criterion in sorted(set(a_scores.keys()) | set(b_scores.keys())):
            a_entry = a_scores.get(criterion)
            b_entry = b_scores.get(criterion)
            a_score = a_entry["score"] if a_entry else None
            b_score = b_entry["score"] if b_entry else None
            if (
                not isinstance(a_score, bool)
                and not isinstance(b_score, bool)
                and isinstance(a_score, (int, float))
                and isinstance(b_score, (int, float))
            ):
                delta: float | None = b_score - a_score
            else:
                delta = None
            score_deltas[criterion] = ScoreDelta(a=a_score, b=b_score, delta=delta)

        comparisons.append(
            CaseComparison(
                case_id=case_id,
                a_passed=a_passed,
                b_passed=b_passed,
                flipped=flipped,
                score_deltas=score_deltas,
            )
        )

    return RunComparison(
        run_a=RunSummary.model_validate(run_a),
        run_b=RunSummary.model_validate(run_b),
        cases=comparisons,
    )


@app.get("/runs", response_model=list[RunSummary])
def list_runs(db: Session = Depends(get_db)):
    return db.query(Run).order_by(Run.started_at.desc()).all()


@app.get("/runs/{run_id}", response_model=RunDetail)
def get_run(run_id: str, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    cases = db.query(CaseResult).filter(CaseResult.run_id == run_id).all()
    return RunDetail.model_validate(
        {
            "id": run.id,
            "suite_id": run.suite_id,
            "status": run.status,
            "git_sha": run.git_sha,
            "agent_version": run.agent_version,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "total_cases": run.total_cases,
            "passed_cases": run.passed_cases,
            "cases": [CaseResultResponse.model_validate(c) for c in cases],
        }
    )


@app.get("/runs/{run_id}/stream")
def stream_run(run_id: str, db: Session = Depends(get_db)):
    if not db.get(Run, run_id):
        raise HTTPException(status_code=404, detail="Run not found")

    async def event_gen():
        seen: set[str] = set()
        for _ in range(600):  # 5-minute hard cap (600 × 0.5 s)
            session = SessionLocal()
            try:
                run_row = session.get(Run, run_id)
                cases = session.query(CaseResult).filter(CaseResult.run_id == run_id).all()
            finally:
                session.close()

            for c in cases:
                if c.id not in seen:
                    seen.add(c.id)
                    event = {
                        "type": "progress",
                        "case_id": c.case_id,
                        "passed": c.passed,
                        "completed": len(seen),
                        "total": run_row.total_cases,
                    }
                    yield f"data: {json.dumps(event)}\n\n"

            if run_row.status in ("completed", "failed"):
                yield f"data: {json.dumps({'type': 'done', 'status': run_row.status, 'run_id': run_id})}\n\n"
                return

            await asyncio.sleep(0.5)

    return StreamingResponse(event_gen(), media_type="text/event-stream")
