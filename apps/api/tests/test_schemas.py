# Tests for rubric and dataset schema loading and validation

import pytest
from pathlib import Path
from pydantic import ValidationError
from api.schemas import load_rubric, load_dataset, Rubric, DatasetCase

EXAMPLES = Path(__file__).parents[3] / "examples" / "support-agent"


class TestLoadRubric:
    def test_loads_example_rubric(self):
        rubric = load_rubric(EXAMPLES / "rubric.yaml")
        assert rubric.name == "support-agent-rubric"
        assert len(rubric.criteria) >= 1

    def test_all_criterion_ids_present(self):
        rubric = load_rubric(EXAMPLES / "rubric.yaml")
        ids = {c.id for c in rubric.criteria}
        assert {"helpfulness", "accuracy", "pii_leaked"}.issubset(ids)

    def test_scale_criterion_fields(self):
        rubric = load_rubric(EXAMPLES / "rubric.yaml")
        helpfulness = next(c for c in rubric.criteria if c.id == "helpfulness")
        assert helpfulness.type == "scale"
        assert helpfulness.scale.min < helpfulness.scale.max

    def test_bool_criterion_invert(self):
        rubric = load_rubric(EXAMPLES / "rubric.yaml")
        pii = next(c for c in rubric.criteria if c.id == "pii_leaked")
        assert pii.type == "bool"
        assert pii.invert is True

    def test_missing_required_field_raises(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("name: bad\ncriteria:\n  - id: x\n    type: scale\n")  # missing description
        with pytest.raises(ValidationError):
            load_rubric(bad)

    def test_invalid_scale_min_gte_max_raises(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            "name: bad\ncriteria:\n  - id: x\n    type: scale\n"
            "    scale: {min: 5, max: 1}\n    description: test\n"
        )
        with pytest.raises(ValidationError):
            load_rubric(bad)

    def test_duplicate_criterion_ids_raise(self, tmp_path):
        bad = tmp_path / "dup.yaml"
        bad.write_text(
            "name: dup\ncriteria:\n"
            "  - id: x\n    type: bool\n    description: a\n"
            "  - id: x\n    type: bool\n    description: b\n"
        )
        with pytest.raises(ValidationError):
            load_rubric(bad)

    def test_unknown_criterion_type_raises(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            "name: bad\ncriteria:\n  - id: x\n    type: emoji\n    description: huh\n"
        )
        with pytest.raises(ValidationError):
            load_rubric(bad)


class TestLoadDataset:
    def test_loads_example_dataset(self):
        cases = load_dataset(EXAMPLES / "dataset.jsonl")
        assert len(cases) == 15

    def test_case_fields(self):
        cases = load_dataset(EXAMPLES / "dataset.jsonl")
        for case in cases:
            assert case.id
            assert case.input
            assert case.expected_behavior

    def test_unique_case_ids(self):
        cases = load_dataset(EXAMPLES / "dataset.jsonl")
        ids = [c.id for c in cases]
        assert len(ids) == len(set(ids))

    def test_invalid_json_line_raises(self, tmp_path):
        bad = tmp_path / "bad.jsonl"
        bad.write_text('{"id": "x", "input": "hi", "expected_behavior": "greet"}\nnot json\n')
        with pytest.raises(ValueError, match="line 2"):
            load_dataset(bad)

    def test_missing_required_field_raises(self, tmp_path):
        bad = tmp_path / "bad.jsonl"
        bad.write_text('{"id": "x", "input": "hi"}\n')  # missing expected_behavior
        with pytest.raises(ValueError):
            load_dataset(bad)

    def test_empty_file_raises(self, tmp_path):
        empty = tmp_path / "empty.jsonl"
        empty.write_text("")
        with pytest.raises(ValueError, match="no cases"):
            load_dataset(empty)

    def test_optional_tool_calls_none(self, tmp_path):
        f = tmp_path / "ok.jsonl"
        f.write_text('{"id": "1", "input": "hi", "expected_behavior": "greet"}\n')
        cases = load_dataset(f)
        assert cases[0].expected_tool_calls is None

    def test_duplicate_case_ids_raise(self, tmp_path):
        f = tmp_path / "dup.jsonl"
        f.write_text(
            '{"id": "x", "input": "a", "expected_behavior": "b"}\n'
            '{"id": "x", "input": "c", "expected_behavior": "d"}\n'
        )
        with pytest.raises(ValueError, match="duplicate ids"):
            load_dataset(f)
