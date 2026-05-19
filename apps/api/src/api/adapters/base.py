"""Core data types and AgentAdapter protocol for RubricLab."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class TraceEvent(BaseModel):
    """A single step in an agent's execution trace."""

    type: Literal["tool_call", "tool_result", "text", "error"]
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    data: dict[str, Any]

    @classmethod
    def tool_call(cls, name: str, inputs: dict[str, Any]) -> "TraceEvent":
        return cls(type="tool_call", data={"name": name, "inputs": inputs})

    @classmethod
    def tool_result(cls, name: str, output: Any, error: str | None = None) -> "TraceEvent":
        return cls(type="tool_result", data={"name": name, "output": output, "error": error})

    @classmethod
    def text(cls, content: str) -> "TraceEvent":
        return cls(type="text", data={"content": content})


class AgentResult(BaseModel):
    """Output of a single agent invocation."""

    output: str
    trace: list[TraceEvent] = Field(default_factory=list)


@runtime_checkable
class AgentAdapter(Protocol):
    """Protocol that all agent adapters must satisfy."""

    def run(self, input: str) -> AgentResult:
        """Run the agent on a single input and return output + trace."""
        ...
