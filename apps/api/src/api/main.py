from __future__ import annotations

import json
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from api.db import get_db, init_db
from api.models import CaseResult, Run


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="RubricLab API", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/runs")
def list_runs(db: Session = Depends(get_db)):
    runs = db.query(Run).order_by(Run.started_at.desc()).all()
    return [
        {
            "id": r.id,
            "suite_id": r.suite_id,
            "status": r.status,
            "git_sha": r.git_sha,
            "agent_version": r.agent_version,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "total_cases": r.total_cases,
            "passed_cases": r.passed_cases,
        }
        for r in runs
    ]


@app.get("/runs/{run_id}")
def get_run(run_id: str, db: Session = Depends(get_db)):
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    cases = db.query(CaseResult).filter(CaseResult.run_id == run_id).all()
    return {
        "id": run.id,
        "suite_id": run.suite_id,
        "status": run.status,
        "git_sha": run.git_sha,
        "agent_version": run.agent_version,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "total_cases": run.total_cases,
        "passed_cases": run.passed_cases,
        "cases": [
            {
                "id": c.id,
                "case_id": c.case_id,
                "agent_output": c.agent_output,
                "trace": json.loads(c.trace_json),
                "rubric_scores": json.loads(c.rubric_scores),
                "deterministic_checks": json.loads(c.deterministic_checks),
                "passed": c.passed,
            }
            for c in cases
        ],
    }
