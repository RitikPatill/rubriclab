"""Deterministic checks that run alongside the LLM judge."""

from __future__ import annotations

import json
import re
from typing import Any

import jsonschema
from pydantic import BaseModel

from api.adapters.base import AgentResult
from api.schemas.dataset import TestCase


class CheckResult(BaseModel):
    name: str
    passed: bool
    detail: str


def check_exact_match(output: str, value: str) -> CheckResult:
    passed = output.strip() == value.strip()
    return CheckResult(
        name="exact_match",
        passed=passed,
        detail="Exact match" if passed else f"Expected {value!r}, got {output!r}",
    )


def check_regex(output: str, pattern: str) -> CheckResult:
    try:
        passed = bool(re.search(pattern, output))
        return CheckResult(
            name=f"regex:{pattern}",
            passed=passed,
            detail=f"Pattern {pattern!r} {'matched' if passed else 'did not match'}",
        )
    except re.error as exc:
        return CheckResult(
            name=f"regex:{pattern}",
            passed=False,
            detail=f"Invalid regex: {exc}",
        )


def check_json_schema(output: str, schema: dict[str, Any]) -> CheckResult:
    try:
        data = json.loads(output)
    except json.JSONDecodeError as exc:
        return CheckResult(name="json_schema", passed=False, detail=f"Invalid JSON: {exc}")
    try:
        jsonschema.validate(data, schema)
        return CheckResult(name="json_schema", passed=True, detail="Validates against schema")
    except jsonschema.ValidationError as exc:
        return CheckResult(name="json_schema", passed=False, detail=f"Schema violation: {exc.message}")


def check_tool_calls(result: AgentResult, expected_tools: list[str]) -> list[CheckResult]:
    """Check that each expected tool was called at least once in the trace."""
    called = {e.data["name"] for e in result.trace if e.type == "tool_call" and "name" in e.data}
    out = []
    for tool in expected_tools:
        passed = tool in called
        out.append(
            CheckResult(
                name=f"tool_call:{tool}",
                passed=passed,
                detail=(
                    f"{tool!r} was called"
                    if passed
                    else f"{tool!r} was not called; called={sorted(called)}"
                ),
            )
        )
    return out


def run_checks(case: TestCase, result: AgentResult) -> list[CheckResult]:
    """Run all deterministic checks defined on a test case."""
    results: list[CheckResult] = []

    for chk in case.checks:
        if chk.type == "exact_match":
            results.append(check_exact_match(result.output, chk.value))
        elif chk.type == "regex":
            results.append(check_regex(result.output, chk.pattern))
        elif chk.type == "json_schema":
            results.append(check_json_schema(result.output, chk.json_schema))

    if case.expected_tool_calls:
        results.extend(check_tool_calls(result, case.expected_tool_calls))

    return results
