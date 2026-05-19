from __future__ import annotations

import pytest

from api.adapters.base import AgentResult, TraceEvent
from api.checks import (
    CheckResult,
    check_exact_match,
    check_json_schema,
    check_regex,
    check_tool_calls,
    run_checks,
)
from api.schemas.dataset import TestCase


# ---------------------------------------------------------------------------
# check_exact_match
# ---------------------------------------------------------------------------


def test_exact_match_pass():
    r = check_exact_match("hello world", "hello world")
    assert r.passed
    assert r.name == "exact_match"


def test_exact_match_fail():
    r = check_exact_match("hello world", "goodbye world")
    assert not r.passed
    assert "goodbye world" in r.detail


def test_exact_match_strips_whitespace():
    r = check_exact_match("  hello  ", "hello")
    assert r.passed


# ---------------------------------------------------------------------------
# check_regex
# ---------------------------------------------------------------------------


def test_regex_match():
    r = check_regex("Order #12345 shipped", r"\d+")
    assert r.passed
    assert "matched" in r.detail


def test_regex_no_match():
    r = check_regex("no numbers here", r"\d+")
    assert not r.passed
    assert "did not match" in r.detail


def test_regex_invalid_pattern():
    r = check_regex("anything", r"[invalid")
    assert not r.passed
    assert "Invalid regex" in r.detail


# ---------------------------------------------------------------------------
# check_json_schema
# ---------------------------------------------------------------------------

_USER_SCHEMA = {
    "type": "object",
    "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
    "required": ["name", "age"],
}


def test_json_schema_valid():
    r = check_json_schema('{"name": "alice", "age": 30}', _USER_SCHEMA)
    assert r.passed
    assert "Validates" in r.detail


def test_json_schema_invalid_json():
    r = check_json_schema("not json at all", _USER_SCHEMA)
    assert not r.passed
    assert "Invalid JSON" in r.detail


def test_json_schema_validation_failure():
    r = check_json_schema('{"age": "not-a-number"}', _USER_SCHEMA)
    assert not r.passed
    assert "Schema violation" in r.detail


# ---------------------------------------------------------------------------
# check_tool_calls
# ---------------------------------------------------------------------------


def _result_with_tools(*names: str) -> AgentResult:
    return AgentResult(
        output="ok",
        trace=[TraceEvent.tool_call(name, {}) for name in names],
    )


def test_tool_calls_present():
    checks = check_tool_calls(_result_with_tools("kb_search"), ["kb_search"])
    assert len(checks) == 1
    assert checks[0].passed
    assert checks[0].name == "tool_call:kb_search"


def test_tool_calls_missing():
    checks = check_tool_calls(AgentResult(output="ok", trace=[]), ["kb_search"])
    assert len(checks) == 1
    assert not checks[0].passed
    assert "was not called" in checks[0].detail


def test_tool_calls_multiple_some_missing():
    result = _result_with_tools("kb_search")
    checks = check_tool_calls(result, ["kb_search", "order_lookup"])
    assert checks[0].passed
    assert not checks[1].passed


# ---------------------------------------------------------------------------
# run_checks
# ---------------------------------------------------------------------------


def _case(**kwargs) -> TestCase:
    defaults = {"id": "t1", "input": "hello", "expected_behavior": "greet user"}
    defaults.update(kwargs)
    return TestCase.model_validate(defaults)


def test_run_checks_no_checks_no_tools():
    case = _case()
    result = AgentResult(output="hi", trace=[])
    assert run_checks(case, result) == []


def test_run_checks_exact_match_pass():
    case = _case(checks=[{"type": "exact_match", "value": "hi"}])
    result = AgentResult(output="hi", trace=[])
    checks = run_checks(case, result)
    assert len(checks) == 1
    assert checks[0].passed


def test_run_checks_regex():
    case = _case(checks=[{"type": "regex", "pattern": r"\d+"}])
    result = AgentResult(output="Order 123", trace=[])
    checks = run_checks(case, result)
    assert checks[0].passed


def test_run_checks_json_schema():
    case = _case(
        checks=[{"type": "json_schema", "schema": {"type": "object", "required": ["id"]}}]
    )
    result = AgentResult(output='{"id": 1}', trace=[])
    checks = run_checks(case, result)
    assert checks[0].passed


def test_run_checks_expected_tool_calls():
    case = _case(expected_tool_calls=["kb_search"])
    result = AgentResult(output="answer", trace=[TraceEvent.tool_call("kb_search", {})])
    checks = run_checks(case, result)
    assert len(checks) == 1
    assert checks[0].passed


def test_run_checks_combined_all_pass():
    case = _case(
        checks=[{"type": "regex", "pattern": r"\d+"}],
        expected_tool_calls=["kb_search"],
    )
    result = AgentResult(
        output="Order 123",
        trace=[TraceEvent.tool_call("kb_search", {})],
    )
    checks = run_checks(case, result)
    assert len(checks) == 2
    assert all(c.passed for c in checks)


def test_run_checks_combined_one_fail():
    case = _case(
        checks=[{"type": "exact_match", "value": "exact text"}],
        expected_tool_calls=["kb_search"],
    )
    result = AgentResult(
        output="different text",
        trace=[TraceEvent.tool_call("kb_search", {})],
    )
    checks = run_checks(case, result)
    assert len(checks) == 2
    assert not checks[0].passed  # exact_match fails
    assert checks[1].passed  # tool call passes
