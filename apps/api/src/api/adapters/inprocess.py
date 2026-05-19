"""In-process adapter: wraps a Python callable as an AgentAdapter."""

from __future__ import annotations

from typing import Callable

from .base import AgentResult


class InProcessAdapter:
    """Wraps a Python callable ``fn(input: str) -> AgentResult``.

    The callable must return an :class:`AgentResult` directly.  If it returns
    a plain ``str`` the adapter normalises it so callers always see a full
    ``AgentResult``.
    """

    def __init__(self, fn: Callable[[str], AgentResult | str]) -> None:
        self._fn = fn

    def run(self, input: str) -> AgentResult:
        result = self._fn(input)
        if isinstance(result, str):
            return AgentResult(output=result)
        return result
