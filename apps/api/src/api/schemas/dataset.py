from __future__ import annotations
import json
from pathlib import Path
from pydantic import BaseModel, ConfigDict, ValidationError

class TestCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    input: str
    expected_behavior: str
    expected_tool_calls: list[str] | None = None
    tags: list[str] = []

DatasetCase = TestCase

def load_dataset(path) -> list[TestCase]:
    path = Path(path)
    cases = []
    errors = []
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                raw = json.loads(stripped)
            except json.JSONDecodeError as exc:
                errors.append("line " + str(lineno) + ": invalid JSON -- " + str(exc))
                continue
            try:
                cases.append(TestCase.model_validate(raw))
            except ValidationError as exc:
                errors.append("line " + str(lineno) + ": " + str(exc))
    if errors:
        raise ValueError(str(path) + ":\n" + "\n".join(errors))
    if not cases:
        raise ValueError("no cases found in " + str(path))
    seen = set()
    dupes = []
    for case in cases:
        if case.id in seen:
            dupes.append(case.id)
        seen.add(case.id)
    if dupes:
        raise ValueError(str(path) + ": duplicate ids: " + ", ".join(dupes))
    return cases
