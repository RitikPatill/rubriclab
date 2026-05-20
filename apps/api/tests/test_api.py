from __future__ import annotations

import itertools
import json
import time
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.db import SessionLocal
from api.main import app
from api.models import CaseResult, Run, Suite

client = TestClient(app)


# ── Test 1: Suite CRUD ────────────────────────────────────────────────────────


def test_create_and_list_suites():
    resp = client.post(
        "/suites",
        json={"name": "s", "rubric_path": "r.yaml", "dataset_path": "d.jsonl"},
    )
    assert resp.status_code == 201
    data = resp.json()
    sid = data["id"]
    assert data["name"] == "s"
    assert data["rubric_path"] == "r.yaml"

    resp = client.get("/suites")
    assert resp.status_code == 200
    assert any(s["id"] == sid for s in resp.json())

    resp = client.get(f"/suites/{sid}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "s"


def test_get_suite_not_found():
    resp = client.get("/suites/nonexistent-id")
    assert resp.status_code == 404


# ── Test 2: Start run, poll, assert scores ────────────────────────────────────


def _fake_run_eval(
    suite,
    rubric,
    dataset,
    adapter,
    db,
    agent_version="unknown",
    judge_config=None,
    judge_client=None,
    run_id=None,
):
    """Synchronous stub: marks the run completed and writes one CaseResult."""
    run = db.query(Run).filter(Run.id == run_id).first()
    run.status = "running"
    db.commit()

    db.add(
        CaseResult(
            id=str(uuid.uuid4()),
            run_id=run.id,
            case_id="case-001",
            agent_output="ok",
            trace_json="[]",
            rubric_scores=json.dumps({"helpfulness": {"score": 4, "reasoning": "good"}}),
            judge_reasoning=json.dumps({"helpfulness": "good"}),
            deterministic_checks=json.dumps([]),
            passed=True,
        )
    )
    run.status = "completed"
    run.passed_cases = 1
    run.completed_at = datetime.now(timezone.utc)
    db.commit()
    return run


def test_start_run_poll_and_assert():
    mock_rubric = MagicMock()
    mock_dataset = [MagicMock()]  # one fake case so total_cases == 1

    with (
        patch("api.main.run_eval", side_effect=_fake_run_eval),
        patch("api.main.load_rubric", return_value=mock_rubric),
        patch("api.main.load_dataset", return_value=mock_dataset),
    ):
        # Create suite (paths don't matter — loaders are mocked)
        resp = client.post(
            "/suites",
            json={"name": "demo", "rubric_path": "x.yaml", "dataset_path": "x.jsonl"},
        )
        assert resp.status_code == 201
        suite_id = resp.json()["id"]

        # Start run — 202 returned immediately
        resp = client.post(
            f"/suites/{suite_id}/runs",
            json={"agent_url": "http://fake-agent/", "agent_version": "v1"},
        )
        assert resp.status_code == 202
        run_id = resp.json()["run_id"]
        assert resp.json()["status"] == "pending"

        # Poll until completed (background task runs quickly with mock)
        r = None
        for _ in range(50):
            r = client.get(f"/runs/{run_id}")
            if r.json()["status"] == "completed":
                break
            time.sleep(0.1)

        assert r is not None
        data = r.json()
        assert data["status"] == "completed"
        assert len(data["cases"]) == 1
        assert data["cases"][0]["case_id"] == "case-001"
        assert data["cases"][0]["rubric_scores"]["helpfulness"]["score"] == 4
        assert data["cases"][0]["passed"] is True


# ── Test 3: SSE endpoint sanity ───────────────────────────────────────────────


def test_stream_returns_event_stream():
    # Create a completed run directly in the DB (no HTTP call needed).
    # Capture IDs as plain strings before closing the session to avoid
    # DetachedInstanceError on expired ORM objects.
    suite_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    db = SessionLocal()
    suite = Suite(
        id=suite_id,
        name="t",
        rubric_path="r.yaml",
        dataset_path="d.jsonl",
    )
    run = Run(
        id=run_id,
        suite_id=suite_id,
        status="completed",
        agent_version="v1",
        total_cases=0,
        passed_cases=0,
    )
    db.add_all([suite, run])
    db.commit()
    db.close()

    with client.stream("GET", f"/runs/{run_id}/stream") as r:
        assert r.status_code == 200
        assert "text/event-stream" in r.headers["content-type"]
        lines = list(itertools.islice(r.iter_lines(), 20))

    assert any("done" in line for line in lines)


def test_stream_run_not_found():
    resp = client.get("/runs/nonexistent-id/stream")
    assert resp.status_code == 404
