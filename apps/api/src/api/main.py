from __future__ import annotations

import asyncio
import json
import uuid
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from api.adapters.http import HttpAdapter
from api.db import SessionLocal, get_db, init_db
from api.models import CaseResult, Run, Suite
from api.runner import _get_git_sha, run_eval
from api.schemas.api import (
    CaseResultResponse,
    RunDetail,
    RunStartRequest,
    RunStartResponse,
    RunSummary,
    SuiteCreate,
    SuiteResponse,
)
from api.schemas.dataset import load_dataset
from api.schemas.rubric import load_rubric


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
