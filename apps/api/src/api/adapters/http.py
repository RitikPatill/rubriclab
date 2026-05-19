"""HTTP adapter: calls a remote agent endpoint."""

from __future__ import annotations

import httpx

from .base import AgentResult


class HttpAdapter:
    """Posts ``{"input": ...}`` to a remote HTTP endpoint and parses the response.

    The remote endpoint must return JSON that is valid for :class:`AgentResult`,
    i.e. ``{"output": "...", "trace": [...]}``.

    Args:
        url: Full URL of the agent endpoint, e.g. ``http://localhost:9000/run``.
        timeout: Request timeout in seconds (default 60).
        headers: Extra HTTP headers to include (e.g. auth tokens).
    """

    def __init__(
        self,
        url: str,
        *,
        timeout: float = 60.0,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._url = url
        self._timeout = timeout
        self._headers = headers or {}

    def run(self, input: str) -> AgentResult:
        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(
                self._url,
                json={"input": input},
                headers=self._headers,
            )
            response.raise_for_status()
            return AgentResult.model_validate(response.json())
