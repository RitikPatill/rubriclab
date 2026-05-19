"""Tests for AgentAdapter protocol, InProcessAdapter, and HttpAdapter."""

from __future__ import annotations

import json

import pytest
import respx
import httpx

from api.adapters import AgentAdapter, AgentResult, InProcessAdapter, HttpAdapter, TraceEvent


# ---------------------------------------------------------------------------
# TraceEvent helpers
# ---------------------------------------------------------------------------


class TestTraceEvent:
    def test_tool_call_factory(self):
        ev = TraceEvent.tool_call("kb_search", {"query": "password"})
        assert ev.type == "tool_call"
        assert ev.data["name"] == "kb_search"
        assert ev.data["inputs"] == {"query": "password"}
        assert ev.timestamp  # non-empty ISO string

    def test_tool_result_factory(self):
        ev = TraceEvent.tool_result("kb_search", {"found": True})
        assert ev.type == "tool_result"
        assert ev.data["output"] == {"found": True}
        assert ev.data["error"] is None

    def test_tool_result_with_error(self):
        ev = TraceEvent.tool_result("kb_search", None, error="timeout")
        assert ev.data["error"] == "timeout"

    def test_text_factory(self):
        ev = TraceEvent.text("Hello!")
        assert ev.type == "text"
        assert ev.data["content"] == "Hello!"

    def test_roundtrip_json(self):
        ev = TraceEvent.tool_call("order_lookup", {"order_id": "123"})
        ev2 = TraceEvent.model_validate_json(ev.model_dump_json())
        assert ev2 == ev


# ---------------------------------------------------------------------------
# AgentResult
# ---------------------------------------------------------------------------


class TestAgentResult:
    def test_minimal(self):
        r = AgentResult(output="Hi")
        assert r.output == "Hi"
        assert r.trace == []

    def test_with_trace(self):
        trace = [TraceEvent.text("thinking")]
        r = AgentResult(output="done", trace=trace)
        assert len(r.trace) == 1

    def test_roundtrip_json(self):
        r = AgentResult(output="ok", trace=[TraceEvent.text("hi")])
        r2 = AgentResult.model_validate_json(r.model_dump_json())
        assert r2 == r


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestAgentAdapterProtocol:
    def test_inprocess_satisfies_protocol(self):
        adapter = InProcessAdapter(lambda x: AgentResult(output=x))
        assert isinstance(adapter, AgentAdapter)

    def test_http_satisfies_protocol(self):
        adapter = HttpAdapter("http://localhost:9000/run")
        assert isinstance(adapter, AgentAdapter)


# ---------------------------------------------------------------------------
# InProcessAdapter
# ---------------------------------------------------------------------------


class TestInProcessAdapter:
    def test_basic_callable(self):
        adapter = InProcessAdapter(lambda x: AgentResult(output=f"echo: {x}"))
        result = adapter.run("hello")
        assert result.output == "echo: hello"
        assert result.trace == []

    def test_normalises_plain_string(self):
        """A callable that returns a plain str is wrapped into AgentResult."""
        adapter = InProcessAdapter(lambda x: x.upper())
        result = adapter.run("hello")
        assert isinstance(result, AgentResult)
        assert result.output == "HELLO"

    def test_preserves_trace(self):
        trace = [TraceEvent.tool_call("kb_search", {"query": "q"})]

        def fn(inp: str) -> AgentResult:
            return AgentResult(output="answer", trace=trace)

        result = InProcessAdapter(fn).run("q?")
        assert len(result.trace) == 1
        assert result.trace[0].type == "tool_call"

    def test_exception_propagates(self):
        def boom(x: str) -> AgentResult:
            raise RuntimeError("kaboom")

        with pytest.raises(RuntimeError, match="kaboom"):
            InProcessAdapter(boom).run("x")


# ---------------------------------------------------------------------------
# HttpAdapter
# ---------------------------------------------------------------------------


class TestHttpAdapter:
    @respx.mock
    def test_success(self):
        payload = {"output": "order found", "trace": []}
        respx.post("http://agent.test/run").mock(
            return_value=httpx.Response(200, json=payload)
        )
        adapter = HttpAdapter("http://agent.test/run")
        result = adapter.run("where is my order?")
        assert result.output == "order found"
        assert result.trace == []

    @respx.mock
    def test_response_with_trace(self):
        trace_event = {
            "type": "tool_call",
            "timestamp": "2026-01-01T00:00:00+00:00",
            "data": {"name": "order_lookup", "inputs": {"order_id": "42"}},
        }
        payload = {"output": "shipped", "trace": [trace_event]}
        respx.post("http://agent.test/run").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = HttpAdapter("http://agent.test/run").run("order?")
        assert len(result.trace) == 1
        assert result.trace[0].type == "tool_call"

    @respx.mock
    def test_sends_input_as_json_body(self):
        route = respx.post("http://agent.test/run").mock(
            return_value=httpx.Response(200, json={"output": "ok", "trace": []})
        )
        HttpAdapter("http://agent.test/run").run("test input")
        sent_body = json.loads(route.calls[0].request.content)
        assert sent_body == {"input": "test input"}

    @respx.mock
    def test_raises_on_http_error(self):
        respx.post("http://agent.test/run").mock(
            return_value=httpx.Response(500, text="internal error")
        )
        with pytest.raises(httpx.HTTPStatusError):
            HttpAdapter("http://agent.test/run").run("boom")

    @respx.mock
    def test_custom_headers_forwarded(self):
        route = respx.post("http://agent.test/run").mock(
            return_value=httpx.Response(200, json={"output": "ok", "trace": []})
        )
        HttpAdapter("http://agent.test/run", headers={"X-Api-Key": "secret"}).run("hi")
        assert route.calls[0].request.headers["X-Api-Key"] == "secret"
