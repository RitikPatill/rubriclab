from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from api.adapters.base import AgentResult, TraceEvent
from api.judge import (
    CriterionScore,
    JudgeConfig,
    JudgeVerdict,
    _aggregate,
    _format_trace,
    _parse_verdict,
    judge,
)
from api.schemas.rubric import BoolCriterion, Rubric, ScaleCriterion, ScaleRange


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _rubric() -> Rubric:
    return Rubric(
        name="test",
        criteria=[
            ScaleCriterion(
                id="helpfulness", type="scale", scale=ScaleRange(min=1, max=5), description="Helpful?"
            ),
            BoolCriterion(id="accurate", type="bool", description="Correct?"),
            BoolCriterion(id="pii_leaked", type="bool", description="PII leaked?", invert=True),
        ],
    )


def _mock_client(response_text: str) -> MagicMock:
    m = MagicMock()
    msg = MagicMock()
    msg.content = [MagicMock(text=response_text)]
    m.messages.create.return_value = msg
    return m


def _verdict_json(
    helpfulness: int = 4,
    accurate: bool = True,
    pii_leaked: bool = False,
) -> str:
    return json.dumps(
        {
            "scores": {
                "helpfulness": {"score": helpfulness, "reasoning": "good"},
                "accurate": {"score": accurate, "reasoning": "yes"},
                "pii_leaked": {"score": pii_leaked, "reasoning": "none"},
            }
        }
    )


# ---------------------------------------------------------------------------
# _format_trace
# ---------------------------------------------------------------------------


def test_format_trace_empty():
    assert _format_trace([]) == "(no trace)"


def test_format_trace_tool_call():
    text = _format_trace([TraceEvent.tool_call("search", {"q": "x"})])
    assert "[TOOL_CALL]" in text
    assert "search" in text


def test_format_trace_tool_result():
    text = _format_trace([TraceEvent.tool_result("search", "the answer")])
    assert "[TOOL_RESULT]" in text
    assert "search" in text


def test_format_trace_text_event():
    text = _format_trace([TraceEvent.text("hello world")])
    assert "[TEXT]" in text
    assert "hello world" in text


def test_format_trace_multiple_events():
    events = [
        TraceEvent.tool_call("kb_search", {"query": "test"}),
        TraceEvent.tool_result("kb_search", "result"),
        TraceEvent.text("Here is what I found"),
    ]
    text = _format_trace(events)
    assert text.count("[TOOL_CALL]") == 1
    assert text.count("[TOOL_RESULT]") == 1
    assert text.count("[TEXT]") == 1


# ---------------------------------------------------------------------------
# _parse_verdict
# ---------------------------------------------------------------------------


def test_parse_verdict_clean_json():
    payload = json.dumps(
        {
            "scores": {
                "helpfulness": {"score": 4, "reasoning": "good"},
                "accurate": {"score": True, "reasoning": "yes"},
            }
        }
    )
    v = _parse_verdict(payload)
    assert v.scores["helpfulness"].score == 4
    assert v.scores["accurate"].score is True


def test_parse_verdict_markdown_fence():
    payload = (
        "```json\n"
        + json.dumps({"scores": {"helpfulness": {"score": 3, "reasoning": "ok"}}})
        + "\n```"
    )
    v = _parse_verdict(payload)
    assert v.scores["helpfulness"].score == 3


def test_parse_verdict_unnamed_fence():
    payload = "```\n" + json.dumps({"scores": {"h": {"score": 2, "reasoning": "r"}}}) + "\n```"
    v = _parse_verdict(payload)
    assert v.scores["h"].score == 2


# ---------------------------------------------------------------------------
# _aggregate
# ---------------------------------------------------------------------------


def _scale_rubric() -> Rubric:
    return Rubric(
        name="t",
        criteria=[
            ScaleCriterion(id="h", type="scale", scale=ScaleRange(min=1, max=5), description="")
        ],
    )


def _bool_rubric() -> Rubric:
    return Rubric(
        name="t",
        criteria=[BoolCriterion(id="a", type="bool", description="")],
    )


def test_aggregate_single_verdict_unchanged():
    rubric = _scale_rubric()
    v = JudgeVerdict(scores={"h": CriterionScore(score=4, reasoning="good")})
    assert _aggregate([v], rubric) is v


def test_aggregate_scale_median_odd():
    rubric = _scale_rubric()
    verdicts = [
        JudgeVerdict(scores={"h": CriterionScore(score=s, reasoning="r")}) for s in [2, 4, 5]
    ]
    agg = _aggregate(verdicts, rubric)
    assert agg.scores["h"].score == 4  # median of [2, 4, 5]


def test_aggregate_scale_median_even():
    rubric = _scale_rubric()
    verdicts = [
        JudgeVerdict(scores={"h": CriterionScore(score=s, reasoning="r")}) for s in [3, 4]
    ]
    agg = _aggregate(verdicts, rubric)
    assert agg.scores["h"].score == 4  # round(3.5) = 4


def test_aggregate_scale_clamped_to_max():
    rubric = _scale_rubric()
    # All score 5 — should stay 5 (max is 5)
    verdicts = [
        JudgeVerdict(scores={"h": CriterionScore(score=5, reasoning="r")}) for _ in range(3)
    ]
    agg = _aggregate(verdicts, rubric)
    assert agg.scores["h"].score == 5


def test_aggregate_bool_majority_true():
    rubric = _bool_rubric()
    verdicts = [
        JudgeVerdict(scores={"a": CriterionScore(score=b, reasoning="r")})
        for b in [True, True, False, True, False]
    ]
    agg = _aggregate(verdicts, rubric)
    assert agg.scores["a"].score is True


def test_aggregate_bool_majority_false():
    rubric = _bool_rubric()
    verdicts = [
        JudgeVerdict(scores={"a": CriterionScore(score=b, reasoning="r")})
        for b in [False, False, True, False, True]
    ]
    agg = _aggregate(verdicts, rubric)
    assert agg.scores["a"].score is False


def test_aggregate_reasoning_includes_sample_count():
    rubric = _scale_rubric()
    verdicts = [
        JudgeVerdict(scores={"h": CriterionScore(score=4, reasoning="r")}) for _ in range(3)
    ]
    agg = _aggregate(verdicts, rubric)
    assert "N=3" in agg.scores["h"].reasoning


# ---------------------------------------------------------------------------
# judge (full function, mocked client)
# ---------------------------------------------------------------------------


def test_judge_single_sample_returns_verdict():
    rubric = _rubric()
    client = _mock_client(_verdict_json())
    result = AgentResult(output="I can help with that!", trace=[])

    verdict = judge(
        rubric=rubric,
        case_input="How do I reset my password?",
        expected_behavior="Explain self-service password reset",
        result=result,
        config=JudgeConfig(samples=1, model="claude-haiku-4-5-20251001"),
        client=client,
    )

    assert verdict.scores["helpfulness"].score == 4
    assert verdict.scores["accurate"].score is True
    assert verdict.scores["pii_leaked"].score is False
    client.messages.create.assert_called_once()


def test_judge_calls_model_with_specified_model():
    rubric = _rubric()
    client = _mock_client(_verdict_json())
    result = AgentResult(output="ok", trace=[])

    judge(
        rubric=rubric,
        case_input="q",
        expected_behavior="e",
        result=result,
        config=JudgeConfig(samples=1, model="claude-opus-4-6"),
        client=client,
    )

    call_kwargs = client.messages.create.call_args
    assert call_kwargs.kwargs["model"] == "claude-opus-4-6"


def test_judge_self_consistency_calls_n_times():
    rubric = Rubric(
        name="t",
        criteria=[
            ScaleCriterion(id="h", type="scale", scale=ScaleRange(min=1, max=5), description="")
        ],
    )
    payloads = [
        json.dumps({"scores": {"h": {"score": s, "reasoning": "r"}}}) for s in [3, 4, 5]
    ]
    client = MagicMock()
    client.messages.create.side_effect = [
        MagicMock(content=[MagicMock(text=p)]) for p in payloads
    ]
    result = AgentResult(output="ok", trace=[])

    verdict = judge(
        rubric=rubric,
        case_input="q",
        expected_behavior="e",
        result=result,
        config=JudgeConfig(samples=3, model="claude-haiku-4-5-20251001"),
        client=client,
    )

    assert verdict.scores["h"].score == 4  # median of [3, 4, 5]
    assert client.messages.create.call_count == 3


def test_judge_includes_trace_in_prompt():
    rubric = _rubric()
    client = _mock_client(_verdict_json())
    result = AgentResult(
        output="Here is the answer",
        trace=[TraceEvent.tool_call("kb_search", {"query": "password"})],
    )

    judge(
        rubric=rubric,
        case_input="q",
        expected_behavior="e",
        result=result,
        config=JudgeConfig(samples=1),
        client=client,
    )

    prompt_content = client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "kb_search" in prompt_content
    assert "TOOL_CALL" in prompt_content
