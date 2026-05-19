from __future__ import annotations

import json
import math
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from api.adapters.base import AgentResult, TraceEvent
from api.checks import CheckResult
from api.judge import CriterionScore, JudgeConfig, JudgeVerdict
from api.models import Base, CaseResult, Run, Suite
from api.runner import _case_passed, _get_git_sha, run_eval
from api.schemas.dataset import TestCase
from api.schemas.rubric import BoolCriterion, Rubric, ScaleCriterion, ScaleRange


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Sess = sessionmaker(bind=engine)
    session = Sess()
    yield session
    session.close()


def _rubric() -> Rubric:
    return Rubric(
        name="test",
        criteria=[
            ScaleCriterion(
                id="helpfulness", type="scale", scale=ScaleRange(min=1, max=5), description="Help?"
            ),
            BoolCriterion(id="accurate", type="bool", description="Correct?"),
            BoolCriterion(id="pii_leaked", type="bool", description="PII?", invert=True),
        ],
    )


def _suite(db: Session) -> Suite:
    s = Suite(
        id=str(uuid.uuid4()),
        name="test-suite",
        rubric_path="r.yaml",
        dataset_path="d.jsonl",
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def _cases(n: int = 2) -> list[TestCase]:
    return [
        TestCase(id=f"case-{i}", input=f"input {i}", expected_behavior=f"expected {i}")
        for i in range(n)
    ]


def _good_verdict() -> JudgeVerdict:
    return JudgeVerdict(
        scores={
            "helpfulness": CriterionScore(score=4, reasoning="good"),
            "accurate": CriterionScore(score=True, reasoning="correct"),
            "pii_leaked": CriterionScore(score=False, reasoning="no PII"),
        }
    )


def _bad_verdict() -> JudgeVerdict:
    return JudgeVerdict(
        scores={
            "helpfulness": CriterionScore(score=2, reasoning="unhelpful"),
            "accurate": CriterionScore(score=False, reasoning="wrong"),
            "pii_leaked": CriterionScore(score=True, reasoning="PII found"),
        }
    )


class _MockAdapter:
    def run(self, input: str) -> AgentResult:
        return AgentResult(output=f"Response to: {input}", trace=[])


# ---------------------------------------------------------------------------
# _case_passed
# ---------------------------------------------------------------------------


def test_case_passed_all_good():
    rubric = _rubric()
    assert _case_passed(_good_verdict(), [], rubric)


def test_case_passed_scale_below_threshold():
    # threshold for scale 1-5 = ceil((1+5)/2) = 3
    rubric = Rubric(
        name="t",
        criteria=[ScaleCriterion(id="h", type="scale", scale=ScaleRange(min=1, max=5), description="")],
    )
    v = JudgeVerdict(scores={"h": CriterionScore(score=2, reasoning="r")})
    assert not _case_passed(v, [], rubric)


def test_case_passed_scale_at_threshold():
    rubric = Rubric(
        name="t",
        criteria=[ScaleCriterion(id="h", type="scale", scale=ScaleRange(min=1, max=5), description="")],
    )
    v = JudgeVerdict(scores={"h": CriterionScore(score=3, reasoning="r")})
    assert _case_passed(v, [], rubric)


def test_case_passed_scale_1_3_threshold():
    # threshold for scale 1-3 = ceil((1+3)/2) = 2
    rubric = Rubric(
        name="t",
        criteria=[ScaleCriterion(id="h", type="scale", scale=ScaleRange(min=1, max=3), description="")],
    )
    assert _case_passed(
        JudgeVerdict(scores={"h": CriterionScore(score=2, reasoning="r")}), [], rubric
    )
    assert not _case_passed(
        JudgeVerdict(scores={"h": CriterionScore(score=1, reasoning="r")}), [], rubric
    )


def test_case_passed_inverted_bool_true_fails():
    rubric = Rubric(
        name="t",
        criteria=[BoolCriterion(id="pii_leaked", type="bool", description="", invert=True)],
    )
    v = JudgeVerdict(scores={"pii_leaked": CriterionScore(score=True, reasoning="r")})
    assert not _case_passed(v, [], rubric)


def test_case_passed_inverted_bool_false_passes():
    rubric = Rubric(
        name="t",
        criteria=[BoolCriterion(id="pii_leaked", type="bool", description="", invert=True)],
    )
    v = JudgeVerdict(scores={"pii_leaked": CriterionScore(score=False, reasoning="r")})
    assert _case_passed(v, [], rubric)


def test_case_passed_failing_deterministic_check():
    rubric = Rubric(
        name="t",
        criteria=[BoolCriterion(id="a", type="bool", description="")],
    )
    v = JudgeVerdict(scores={"a": CriterionScore(score=True, reasoning="r")})
    failing = CheckResult(name="exact_match", passed=False, detail="mismatch")
    assert not _case_passed(v, [failing], rubric)


def test_case_passed_missing_criterion_in_verdict():
    rubric = _rubric()
    # Verdict missing 'accurate'
    v = JudgeVerdict(
        scores={
            "helpfulness": CriterionScore(score=4, reasoning="r"),
            "pii_leaked": CriterionScore(score=False, reasoning="r"),
        }
    )
    assert not _case_passed(v, [], rubric)


# ---------------------------------------------------------------------------
# _get_git_sha
# ---------------------------------------------------------------------------


def test_get_git_sha_returns_sha_or_none():
    sha = _get_git_sha()
    assert sha is None or (isinstance(sha, str) and len(sha) == 40)


# ---------------------------------------------------------------------------
# run_eval
# ---------------------------------------------------------------------------


@patch("api.runner.judge")
def test_run_eval_happy_path(mock_judge, db):
    rubric = _rubric()
    suite = _suite(db)
    mock_judge.return_value = _good_verdict()

    run = run_eval(
        suite=suite,
        rubric=rubric,
        dataset=_cases(2),
        adapter=_MockAdapter(),
        db=db,
        agent_version="v1.0",
    )

    assert run.status == "completed"
    assert run.total_cases == 2
    assert run.passed_cases == 2
    assert run.agent_version == "v1.0"

    case_results = db.query(CaseResult).filter(CaseResult.run_id == run.id).all()
    assert len(case_results) == 2
    assert all(c.passed for c in case_results)


@patch("api.runner.judge")
def test_run_eval_all_fail(mock_judge, db):
    rubric = _rubric()
    suite = _suite(db)
    mock_judge.return_value = _bad_verdict()

    run = run_eval(
        suite=suite,
        rubric=rubric,
        dataset=_cases(2),
        adapter=_MockAdapter(),
        db=db,
    )

    assert run.status == "completed"
    assert run.passed_cases == 0
    case_results = db.query(CaseResult).filter(CaseResult.run_id == run.id).all()
    assert all(not c.passed for c in case_results)


@patch("api.runner.judge")
def test_run_eval_agent_exception_stored(mock_judge, db):
    rubric = _rubric()
    suite = _suite(db)
    mock_judge.return_value = _good_verdict()

    class FailingAdapter:
        def run(self, input: str) -> AgentResult:
            raise RuntimeError("agent crashed")

    run = run_eval(
        suite=suite,
        rubric=rubric,
        dataset=_cases(1),
        adapter=FailingAdapter(),
        db=db,
    )

    assert run.status == "completed"
    cr = db.query(CaseResult).filter(CaseResult.run_id == run.id).first()
    assert cr is not None
    assert "ERROR" in cr.agent_output
    assert "agent crashed" in cr.agent_output


@patch("api.runner.judge")
def test_run_eval_persists_scores_as_json(mock_judge, db):
    rubric = _rubric()
    suite = _suite(db)
    mock_judge.return_value = _good_verdict()

    run = run_eval(
        suite=suite,
        rubric=rubric,
        dataset=_cases(1),
        adapter=_MockAdapter(),
        db=db,
    )

    cr = db.query(CaseResult).filter(CaseResult.run_id == run.id).first()
    scores = json.loads(cr.rubric_scores)
    assert scores["helpfulness"]["score"] == 4
    assert scores["accurate"]["score"] is True
    assert scores["pii_leaked"]["score"] is False


@patch("api.runner.judge")
def test_run_eval_persists_trace(mock_judge, db):
    rubric = _rubric()
    suite = _suite(db)
    mock_judge.return_value = _good_verdict()

    class TracingAdapter:
        def run(self, input: str) -> AgentResult:
            return AgentResult(
                output="done",
                trace=[TraceEvent.tool_call("kb_search", {"query": input})],
            )

    run = run_eval(
        suite=suite,
        rubric=rubric,
        dataset=_cases(1),
        adapter=TracingAdapter(),
        db=db,
    )

    cr = db.query(CaseResult).filter(CaseResult.run_id == run.id).first()
    trace = json.loads(cr.trace_json)
    assert len(trace) == 1
    assert trace[0]["type"] == "tool_call"
    assert trace[0]["data"]["name"] == "kb_search"


@patch("api.runner.judge")
def test_run_eval_run_has_git_sha_field(mock_judge, db):
    rubric = _rubric()
    suite = _suite(db)
    mock_judge.return_value = _good_verdict()

    run = run_eval(
        suite=suite,
        rubric=rubric,
        dataset=_cases(1),
        adapter=_MockAdapter(),
        db=db,
    )

    # git_sha is either a valid SHA or None (not in a git repo)
    assert run.git_sha is None or (isinstance(run.git_sha, str) and len(run.git_sha) == 40)


@patch("api.runner.judge")
def test_run_eval_judge_receives_correct_args(mock_judge, db):
    rubric = _rubric()
    suite = _suite(db)
    mock_judge.return_value = _good_verdict()

    cases = _cases(1)
    run_eval(
        suite=suite,
        rubric=rubric,
        dataset=cases,
        adapter=_MockAdapter(),
        db=db,
    )

    call_kwargs = mock_judge.call_args.kwargs
    assert call_kwargs["rubric"] is rubric
    assert call_kwargs["case_input"] == cases[0].input
    assert call_kwargs["expected_behavior"] == cases[0].expected_behavior


@patch("api.runner.judge")
def test_run_eval_partial_results_on_judge_error(mock_judge, db):
    """If the judge raises after some cases, run status is 'failed' but prior rows survive."""
    rubric = _rubric()
    suite = _suite(db)
    mock_judge.side_effect = [_good_verdict(), RuntimeError("judge exploded")]

    with pytest.raises(RuntimeError, match="judge exploded"):
        run_eval(
            suite=suite,
            rubric=rubric,
            dataset=_cases(2),
            adapter=_MockAdapter(),
            db=db,
        )

    run = db.query(Run).filter(Run.suite_id == suite.id).first()
    assert run.status == "failed"
    # First case was committed before the error
    saved = db.query(CaseResult).filter(CaseResult.run_id == run.id).all()
    assert len(saved) == 1
