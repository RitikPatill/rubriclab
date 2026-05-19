from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Suite(Base):
    __tablename__ = "suites"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    rubric_path = Column(String, nullable=False)
    dataset_path = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    runs = relationship("Run", back_populates="suite")


class Run(Base):
    __tablename__ = "runs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    suite_id = Column(String, ForeignKey("suites.id"), nullable=False)
    status = Column(String, nullable=False, default="pending")
    git_sha = Column(String, nullable=True)
    agent_version = Column(String, nullable=False, default="unknown")
    started_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    total_cases = Column(Integer, nullable=False, default=0)
    passed_cases = Column(Integer, nullable=False, default=0)

    suite = relationship("Suite", back_populates="runs")
    case_results = relationship("CaseResult", back_populates="run")


class CaseResult(Base):
    __tablename__ = "case_results"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, ForeignKey("runs.id"), nullable=False)
    case_id = Column(String, nullable=False)
    agent_output = Column(Text, nullable=False)
    trace_json = Column(Text, nullable=False)
    rubric_scores = Column(Text, nullable=False)
    judge_reasoning = Column(Text, nullable=False)
    deterministic_checks = Column(Text, nullable=False)
    passed = Column(Boolean, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    run = relationship("Run", back_populates="case_results")
