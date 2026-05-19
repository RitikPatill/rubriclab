"""Eval runner: iterates test cases, invokes agent, checks, judges, persists."""

from __future__ import annotations

import json
import math
import subprocess
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from api.adapters.base import AgentAdapter, AgentResult
from api.checks import CheckResult, run_checks
from api.judge import JudgeConfig, JudgeVerdict, judge
from api.models import CaseResult, Run, Suite
from api.schemas.dataset import TestCase
from api.schemas.rubric import Rubric


def _get_git_sha() -> str | None:
    """Return the current HEAD commit SHA, or None if not in a git repo."""
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def _case_passed(
    verdict: JudgeVerdict,
    checks: list[CheckResult],
    rubric: Rubric,
) -> bool:
    """Return True iff all deterministic checks and all judge criteria pass.

    Pass thresholds:
    - scale criterion: score >= ceil((min + max) / 2)
    - bool criterion (normal): score == True
    - bool criterion (inverted): score == False
    """
    if any(not c.passed for c in checks):
        return False

    for c in rubric.criteria:
        cid = c.id
        if cid not in verdict.scores:
            return False
        score = verdict.scores[cid].score
        if c.type == "scale":
            threshold = math.ceil((c.scale.min + c.scale.max) / 2)
            if score < threshold:
                return False
        else:  # bool
            expected = not c.invert  # True for normal, False for inverted
            if score != expected:
                return False

    return True


def run_eval(
    suite: Suite,
    rubric: Rubric,
    dataset: list[TestCase],
    adapter: AgentAdapter,
    db: Session,
    agent_version: str = "unknown",
    judge_config: JudgeConfig | None = None,
    judge_client=None,
) -> Run:
    """Execute a full evaluation run and persist results to the database.

    Args:
        suite: The Suite record this run belongs to.
        rubric: The evaluation rubric.
        dataset: List of test cases to evaluate.
        adapter: Agent adapter to invoke for each case.
        db: SQLAlchemy session for persistence.
        agent_version: Human-readable version tag for the agent under test.
        judge_config: LLM judge settings (model, N samples).
        judge_client: Optional pre-built Anthropic client (for testing).

    Returns:
        The completed Run record.
    """
    if judge_config is None:
        judge_config = JudgeConfig()

    run = Run(
        id=str(uuid.uuid4()),
        suite_id=suite.id,
        status="running",
        git_sha=_get_git_sha(),
        agent_version=agent_version,
        started_at=datetime.now(timezone.utc),
        total_cases=len(dataset),
        passed_cases=0,
    )
    db.add(run)
    db.commit()

    passed = 0
    try:
        for case in dataset:
            # Invoke agent (catch any exception so one bad case doesn't abort the run)
            try:
                result = adapter.run(case.input)
            except Exception as exc:
                result = AgentResult(output=f"ERROR: {exc}", trace=[])

            # Deterministic checks
            checks = run_checks(case, result)

            # LLM judge
            verdict = judge(
                rubric=rubric,
                case_input=case.input,
                expected_behavior=case.expected_behavior,
                result=result,
                config=judge_config,
                client=judge_client,
            )

            ok = _case_passed(verdict, checks, rubric)
            if ok:
                passed += 1

            db.add(
                CaseResult(
                    id=str(uuid.uuid4()),
                    run_id=run.id,
                    case_id=case.id,
                    agent_output=result.output,
                    trace_json=json.dumps([e.model_dump() for e in result.trace]),
                    rubric_scores=json.dumps(
                        {
                            cid: {"score": s.score, "reasoning": s.reasoning}
                            for cid, s in verdict.scores.items()
                        }
                    ),
                    judge_reasoning=json.dumps(
                        {cid: s.reasoning for cid, s in verdict.scores.items()}
                    ),
                    deterministic_checks=json.dumps(
                        [{"name": c.name, "passed": c.passed, "detail": c.detail} for c in checks]
                    ),
                    passed=ok,
                    created_at=datetime.now(timezone.utc),
                )
            )
            db.commit()

    except Exception:
        run.status = "failed"
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
        raise

    run.status = "completed"
    run.completed_at = datetime.now(timezone.utc)
    run.passed_cases = passed
    db.commit()
    return run
