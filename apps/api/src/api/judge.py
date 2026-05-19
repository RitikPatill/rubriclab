"""LLM-as-judge: calls Claude to score agent output against a rubric."""

from __future__ import annotations

import json
import statistics

import anthropic
from pydantic import BaseModel

from api.adapters.base import AgentResult, TraceEvent
from api.schemas.rubric import Rubric


class CriterionScore(BaseModel):
    score: int | bool
    reasoning: str


class JudgeVerdict(BaseModel):
    scores: dict[str, CriterionScore]


class JudgeConfig(BaseModel):
    samples: int = 1
    model: str = "claude-haiku-4-5-20251001"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _format_trace(trace: list[TraceEvent]) -> str:
    if not trace:
        return "(no trace)"
    lines = []
    for e in trace:
        if e.type == "tool_call":
            inputs_str = json.dumps(e.data.get("inputs", {}))
            lines.append(f"[TOOL_CALL] {e.data.get('name')} inputs={inputs_str}")
        elif e.type == "tool_result":
            out = str(e.data.get("output", ""))[:300]
            lines.append(f"[TOOL_RESULT] {e.data.get('name')} output={out}")
        elif e.type == "text":
            content = e.data.get("content", "")[:400]
            if content:
                lines.append(f"[TEXT] {content}")
        elif e.type == "error":
            lines.append(f"[ERROR] {e.data}")
    return "\n".join(lines)


def _build_prompt(
    rubric: Rubric,
    case_input: str,
    expected_behavior: str,
    output: str,
    trace_str: str,
) -> str:
    criteria_lines: list[str] = []
    schema_lines: list[str] = []

    for c in rubric.criteria:
        if c.type == "scale":
            criteria_lines.append(
                f"- {c.id} (scale {c.scale.min}–{c.scale.max}): {c.description}"
            )
            schema_lines.append(
                f'    "{c.id}": {{"score": <int {c.scale.min}-{c.scale.max}>, "reasoning": "<string>"}}'
            )
        else:
            note = " [inverted: True means bad outcome]" if c.invert else ""
            criteria_lines.append(f"- {c.id} (bool{note}): {c.description}")
            schema_lines.append(
                f'    "{c.id}": {{"score": <true|false>, "reasoning": "<string>"}}'
            )

    criteria_str = "\n".join(criteria_lines)
    score_schema = '{{\n  "scores": {{\n{lines}\n  }}\n}}'.format(
        lines=",\n".join(schema_lines)
    )

    return f"""You are a strict evaluator grading an AI agent's response.

## User Input
{case_input}

## Expected Behavior
{expected_behavior}

## Agent Output
{output}

## Agent Trace
{trace_str}

## Rubric
{criteria_str}

Score every criterion. Return ONLY valid JSON — no prose, no markdown fences:
{score_schema}"""


def _parse_verdict(text: str) -> JudgeVerdict:
    """Parse the judge's JSON response into a JudgeVerdict."""
    text = text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.splitlines()
        # Drop opening fence line; also drop closing fence if present
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(inner)

    data = json.loads(text)
    scores: dict[str, CriterionScore] = {}
    for cid, val in data["scores"].items():
        scores[cid] = CriterionScore(score=val["score"], reasoning=val["reasoning"])
    return JudgeVerdict(scores=scores)


def _aggregate(verdicts: list[JudgeVerdict], rubric: Rubric) -> JudgeVerdict:
    """Aggregate N verdicts via self-consistency: median for scale, majority for bool."""
    if len(verdicts) == 1:
        return verdicts[0]

    scores: dict[str, CriterionScore] = {}
    for c in rubric.criteria:
        cid = c.id
        valid = [v.scores[cid] for v in verdicts if cid in v.scores]
        if not valid:
            continue

        raw_scores = [s.score for s in valid]
        first_reason = valid[0].reasoning

        if c.type == "scale":
            agg: int | bool = max(
                c.scale.min,
                min(c.scale.max, round(statistics.median(raw_scores))),  # type: ignore[arg-type]
            )
            reasoning = f"[self-consistency N={len(verdicts)}, median={agg}] {first_reason}"
        else:
            true_count = sum(1 for s in raw_scores if s)
            agg = true_count > len(raw_scores) / 2
            reasoning = (
                f"[self-consistency N={len(verdicts)}, votes={true_count}/{len(raw_scores)}]"
                f" {first_reason}"
            )

        scores[cid] = CriterionScore(score=agg, reasoning=reasoning)

    return JudgeVerdict(scores=scores)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def judge(
    rubric: Rubric,
    case_input: str,
    expected_behavior: str,
    result: AgentResult,
    config: JudgeConfig | None = None,
    client: anthropic.Anthropic | None = None,
) -> JudgeVerdict:
    """Call Claude to score the agent output against every rubric criterion.

    Args:
        rubric: The evaluation rubric.
        case_input: The original user input for the test case.
        expected_behavior: What the agent should have done.
        result: The agent's output and execution trace.
        config: Judge settings (model, number of self-consistency samples).
        client: Optional pre-built Anthropic client (useful for testing).

    Returns:
        A JudgeVerdict with one CriterionScore per rubric criterion.
    """
    if config is None:
        config = JudgeConfig()
    if client is None:
        client = anthropic.Anthropic()

    trace_str = _format_trace(result.trace)
    prompt = _build_prompt(
        rubric=rubric,
        case_input=case_input,
        expected_behavior=expected_behavior,
        output=result.output,
        trace_str=trace_str,
    )

    verdicts: list[JudgeVerdict] = []
    for _ in range(config.samples):
        resp = client.messages.create(
            model=config.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        verdicts.append(_parse_verdict(resp.content[0].text))

    return _aggregate(verdicts, rubric)
