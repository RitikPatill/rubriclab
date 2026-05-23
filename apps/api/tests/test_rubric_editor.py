from __future__ import annotations

import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from api.db import SessionLocal
from api.main import app
from api.models import Suite

client = TestClient(app)

VALID_RUBRIC = """\
name: test-rubric
description: A test rubric
criteria:
  - id: helpfulness
    type: scale
    description: How helpful is the response?
    scale:
      min: 1
      max: 5
"""


def _seed_suite(db, rubric_path: str, dataset_path: str = "d.jsonl") -> Suite:
    suite = Suite(
        id=str(uuid.uuid4()),
        name="rubric-editor-test",
        rubric_path=rubric_path,
        dataset_path=dataset_path,
    )
    db.add(suite)
    db.commit()
    db.refresh(suite)
    return suite


def test_get_rubric(tmp_path: Path):
    rubric_file = tmp_path / "rubric.yaml"
    rubric_file.write_text(VALID_RUBRIC, encoding="utf-8")

    db = SessionLocal()
    suite = _seed_suite(db, str(rubric_file))
    db.close()

    resp = client.get(f"/suites/{suite.id}/rubric")
    assert resp.status_code == 200
    data = resp.json()
    assert data["content"] == VALID_RUBRIC
    assert data["path"] == str(rubric_file)


def test_update_rubric_valid(tmp_path: Path):
    rubric_file = tmp_path / "rubric.yaml"
    rubric_file.write_text(VALID_RUBRIC, encoding="utf-8")

    db = SessionLocal()
    suite = _seed_suite(db, str(rubric_file))
    db.close()

    new_content = VALID_RUBRIC.replace("test-rubric", "updated-rubric")
    resp = client.put(f"/suites/{suite.id}/rubric", json={"content": new_content})
    assert resp.status_code == 200
    data = resp.json()
    assert "updated-rubric" in data["content"]
    # Verify the file was actually written to disk
    assert "updated-rubric" in rubric_file.read_text(encoding="utf-8")


def test_update_rubric_invalid(tmp_path: Path):
    rubric_file = tmp_path / "rubric.yaml"
    rubric_file.write_text(VALID_RUBRIC, encoding="utf-8")

    db = SessionLocal()
    suite = _seed_suite(db, str(rubric_file))
    db.close()

    # Valid YAML syntax but fails schema validation (missing criteria)
    bad_content = "name: broken-no-criteria\n"
    resp = client.put(f"/suites/{suite.id}/rubric", json={"content": bad_content})
    assert resp.status_code == 422


def test_clone_suite(tmp_path: Path):
    rubric_file = tmp_path / "rubric.yaml"
    rubric_file.write_text(VALID_RUBRIC, encoding="utf-8")

    db = SessionLocal()
    suite = _seed_suite(db, str(rubric_file), dataset_path="shared.jsonl")
    db.close()

    resp = client.post(f"/suites/{suite.id}/clone", json={"name": "v2"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] != suite.id
    # Clone shares the same dataset path
    assert data["dataset_path"] == "shared.jsonl"
    # New rubric file was created and name contains "v2"
    new_rubric_path = data["rubric_path"]
    assert "v2" in new_rubric_path
    assert Path(new_rubric_path).exists()


def test_get_rubric_missing_file(tmp_path: Path):
    nonexistent = str(tmp_path / "nonexistent.yaml")

    db = SessionLocal()
    suite = _seed_suite(db, nonexistent)
    db.close()

    resp = client.get(f"/suites/{suite.id}/rubric")
    assert resp.status_code == 404
