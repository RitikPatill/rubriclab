from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient

from api.db import SessionLocal
from api.main import app
from api.models import CaseResult, Run, Suite

client = TestClient(app)


def _seed_suite(db) -> str:
    """Returns suite ID string."""
    suite = Suite(
        id=str(uuid.uuid4()),
        name="compare-test-suite",
        rubric_path="r.yaml",
        dataset_path="d.jsonl",
    )
    db.add(suite)
    db.commit()
    return suite.id


def _seed_run(db, suite_id: str) -> str:
    """Returns run ID string."""
    run = Run(
        id=str(uuid.uuid4()),
        suite_id=suite_id,
        status="completed",
        agent_version="v1",
        total_cases=2,
        passed_cases=1,
    )
    db.add(run)
    db.commit()
    return run.id


def _seed_case(
    db,
    run_id: str,
    case_id: str,
    passed: bool,
    helpfulness: int,
    pii_leaked: bool,
) -> None:
    scores = {
        "helpfulness": {"score": helpfulness, "reasoning": "test"},
        "pii_leaked": {"score": pii_leaked, "reasoning": "test"},
    }
    cr = CaseResult(
        id=str(uuid.uuid4()),
        run_id=run_id,
        case_id=case_id,
        agent_output="output",
        trace_json="[]",
        rubric_scores=json.dumps(scores),
        judge_reasoning=json.dumps({}),
        deterministic_checks=json.dumps([]),
        passed=passed,
    )
    db.add(cr)
    db.commit()


def test_compare_basic():
    db = SessionLocal()
    suite_id = _seed_suite(db)
    run_a_id = _seed_run(db, suite_id)
    run_b_id = _seed_run(db, suite_id)
    # case-1: both pass, helpfulness improves (+1)
    _seed_case(db, run_a_id, "case-1", True, 4, False)
    _seed_case(db, run_b_id, "case-1", True, 5, False)
    # case-2: flips from pass to fail, helpfulness drops (-1)
    _seed_case(db, run_a_id, "case-2", True, 3, False)
    _seed_case(db, run_b_id, "case-2", False, 2, False)
    db.close()

    resp = client.get(f"/runs/compare?a={run_a_id}&b={run_b_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["run_a"]["id"] == run_a_id
    assert data["run_b"]["id"] == run_b_id
    assert len(data["cases"]) == 2

    case1 = next(c for c in data["cases"] if c["case_id"] == "case-1")
    assert case1["flipped"] is False
    assert case1["score_deltas"]["helpfulness"]["delta"] == 1.0  # 5 - 4

    case2 = next(c for c in data["cases"] if c["case_id"] == "case-2")
    assert case2["flipped"] is True
    assert case2["score_deltas"]["helpfulness"]["delta"] == -1.0  # 2 - 3


def test_compare_flipped_flag():
    db = SessionLocal()
    suite_id = _seed_suite(db)
    run_a_id = _seed_run(db, suite_id)
    run_b_id = _seed_run(db, suite_id)
    _seed_case(db, run_a_id, "case-flip", True, 4, False)
    _seed_case(db, run_b_id, "case-flip", False, 2, False)
    db.close()

    resp = client.get(f"/runs/compare?a={run_a_id}&b={run_b_id}")
    assert resp.status_code == 200
    cases = resp.json()["cases"]
    case = next(c for c in cases if c["case_id"] == "case-flip")
    assert case["flipped"] is True
    assert case["a_passed"] is True
    assert case["b_passed"] is False


def test_compare_missing_run():
    resp = client.get("/runs/compare?a=bad-id&b=also-bad")
    assert resp.status_code == 404


def test_compare_bool_delta_is_null():
    db = SessionLocal()
    suite_id = _seed_suite(db)
    run_a_id = _seed_run(db, suite_id)
    run_b_id = _seed_run(db, suite_id)
    # pii_leaked is a bool — delta should be null
    _seed_case(db, run_a_id, "case-bool", True, 4, False)
    _seed_case(db, run_b_id, "case-bool", True, 4, True)
    db.close()

    resp = client.get(f"/runs/compare?a={run_a_id}&b={run_b_id}")
    assert resp.status_code == 200
    cases = resp.json()["cases"]
    case = next(c for c in cases if c["case_id"] == "case-bool")
    assert case["score_deltas"]["pii_leaked"]["delta"] is None
