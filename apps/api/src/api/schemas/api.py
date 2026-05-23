from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator


class SuiteCreate(BaseModel):
    name: str
    rubric_path: str
    dataset_path: str


class SuiteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    rubric_path: str
    dataset_path: str
    created_at: datetime


class RunStartRequest(BaseModel):
    agent_url: str
    agent_version: str = "unknown"


class RunStartResponse(BaseModel):
    run_id: str
    status: str


class RunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    suite_id: str
    status: str
    git_sha: str | None
    agent_version: str
    started_at: datetime
    completed_at: datetime | None
    total_cases: int
    passed_cases: int


class CaseResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    agent_output: str
    trace: list[dict[str, Any]]
    rubric_scores: dict[str, Any]
    deterministic_checks: list[dict[str, Any]]
    passed: bool

    @model_validator(mode="before")
    @classmethod
    def parse_json_fields(cls, data: Any) -> Any:
        if hasattr(data, "trace_json"):
            # ORM CaseResult object — remap column names and parse JSON text fields
            return {
                "id": data.id,
                "case_id": data.case_id,
                "agent_output": data.agent_output,
                "trace": json.loads(data.trace_json) if isinstance(data.trace_json, str) else data.trace_json,
                "rubric_scores": json.loads(data.rubric_scores) if isinstance(data.rubric_scores, str) else data.rubric_scores,
                "deterministic_checks": json.loads(data.deterministic_checks) if isinstance(data.deterministic_checks, str) else data.deterministic_checks,
                "passed": data.passed,
            }
        if isinstance(data, dict):
            data = dict(data)
            if "trace_json" in data and "trace" not in data:
                val = data.pop("trace_json")
                data["trace"] = json.loads(val) if isinstance(val, str) else val
            for field in ("rubric_scores", "deterministic_checks"):
                if field in data and isinstance(data[field], str):
                    data[field] = json.loads(data[field])
        return data


class RunDetail(RunSummary):
    cases: list[CaseResultResponse]


class ScoreDelta(BaseModel):
    a: int | bool | None
    b: int | bool | None
    delta: float | None  # b - a for numeric; None for bool or missing


class CaseComparison(BaseModel):
    case_id: str
    a_passed: bool | None  # None = case absent in that run
    b_passed: bool | None
    flipped: bool  # True when both present and a_passed != b_passed
    score_deltas: dict[str, ScoreDelta]


class RunComparison(BaseModel):
    run_a: RunSummary
    run_b: RunSummary
    cases: list[CaseComparison]


class RubricContent(BaseModel):
    content: str  # raw YAML text
    path: str  # absolute file path (informational)


class RubricUpdate(BaseModel):
    content: str


class CloneSuiteRequest(BaseModel):
    name: str
