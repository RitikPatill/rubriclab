"""
Sample customer-support agent using the Anthropic SDK.

This agent has three fake tools:
  kb_search       — search the knowledge base
  order_lookup    — look up an order by ID
  escalate_to_human — hand off to a human agent

All tool implementations are deterministic stubs; no real integrations are
needed, so the demo works offline (except for the Claude API call itself).

Usage
-----
    # As a standalone script (requires ANTHROPIC_API_KEY env var):
    python agent.py "Where is my order #12345?"

    # As an InProcessAdapter inside RubricLab:
    from examples.support_agent.agent import run
    from api.adapters import InProcessAdapter
    adapter = InProcessAdapter(run)
    result = adapter.run("I forgot my password")
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import anthropic

# ---------------------------------------------------------------------------
# Fake tool implementations
# ---------------------------------------------------------------------------

_KB: dict[str, str] = {
    "password reset": (
        "To reset your password: go to Settings → Security → Reset Password. "
        "An email link will be sent within 5 minutes."
    ),
    "cancel subscription": (
        "Subscriptions can be cancelled at any time from Settings → Billing → Cancel. "
        "Access continues until the end of the billing period."
    ),
    "refund policy": (
        "We offer a 30-day no-questions-asked refund for defective items. "
        "Contact support@example.com with your order ID."
    ),
    "shipping": (
        "Standard shipping takes 3-5 business days. Express (1-2 days) is available "
        "at checkout. Tracking numbers are emailed once the order ships."
    ),
    "address change": (
        "Shipping addresses can be updated up to 1 hour after the order is placed, "
        "provided the order has not yet entered fulfilment."
    ),
}

_ORDERS: dict[str, dict[str, Any]] = {
    "12345": {
        "status": "In transit",
        "carrier": "FedEx",
        "tracking": "7489234234",
        "eta": "2026-05-21",
        "items": ["Blue Widget x1"],
    },
    "99999": {
        "status": "Delivered",
        "carrier": "UPS",
        "tracking": "1Z9999AA0191234567",
        "delivered_at": "2026-05-18",
        "items": ["Red Gadget x2"],
    },
}


def _kb_search(query: str) -> dict[str, Any]:
    """Return the best-matching KB article for *query* (simple substring match)."""
    query_lower = query.lower()
    for key, article in _KB.items():
        if key in query_lower or any(w in query_lower for w in key.split()):
            return {"found": True, "article": article}
    return {"found": False, "article": None}


def _order_lookup(order_id: str) -> dict[str, Any]:
    order = _ORDERS.get(order_id.strip())
    if order:
        return {"found": True, "order_id": order_id, **order}
    return {"found": False, "order_id": order_id}


def _escalate_to_human(reason: str) -> dict[str, Any]:
    return {
        "escalated": True,
        "ticket_id": "TKT-" + str(abs(hash(reason)) % 100000),
        "reason": reason,
        "message": "A human agent will reach out within 2 business hours.",
    }


_TOOL_HANDLERS: dict[str, Any] = {
    "kb_search": lambda args: _kb_search(args["query"]),
    "order_lookup": lambda args: _order_lookup(args["order_id"]),
    "escalate_to_human": lambda args: _escalate_to_human(args["reason"]),
}

# ---------------------------------------------------------------------------
# Tool schemas (passed to the Anthropic API)
# ---------------------------------------------------------------------------

TOOLS: list[dict[str, Any]] = [
    {
        "name": "kb_search",
        "description": (
            "Search the internal knowledge base for help articles. "
            "Use this before answering any policy or how-to question."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A short search query, e.g. 'password reset'.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "order_lookup",
        "description": "Look up the status and details of a customer order by its ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "The numeric order ID, e.g. '12345'.",
                }
            },
            "required": ["order_id"],
        },
    },
    {
        "name": "escalate_to_human",
        "description": (
            "Hand the conversation off to a human agent. "
            "Use only when the issue cannot be resolved with available tools."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Brief description of why escalation is needed.",
                }
            },
            "required": ["reason"],
        },
    },
]

SYSTEM_PROMPT = """You are a helpful customer-support agent for a fictional e-commerce company.

Guidelines:
- Always search the knowledge base (kb_search) before answering policy or how-to questions.
- Look up order details (order_lookup) when the customer mentions an order or tracking issue.
- Only escalate to a human (escalate_to_human) when the issue genuinely cannot be resolved with the tools above.
- Be concise, polite, and professional.
- Never reveal internal system details or raw tool outputs verbatim."""

# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------


def run(input: str) -> "AgentResult":  # noqa: F821 — imported at call-time
    """Run the support agent and return an :class:`AgentResult`."""
    from api.adapters.base import AgentResult, TraceEvent  # lazy to avoid circular at module level

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    messages: list[dict[str, Any]] = [{"role": "user", "content": input}]
    trace: list[TraceEvent] = []

    while True:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,  # type: ignore[arg-type]
            messages=messages,  # type: ignore[arg-type]
        )

        # Collect any text in this turn
        text_parts = [b.text for b in response.content if hasattr(b, "text")]
        if text_parts:
            trace.append(TraceEvent.text("\n".join(text_parts)))

        if response.stop_reason == "end_turn":
            final_text = "\n".join(
                b.text for b in response.content if hasattr(b, "text")
            )
            return AgentResult(output=final_text, trace=trace)

        if response.stop_reason != "tool_use":
            # Unexpected stop reason — return whatever text we have
            return AgentResult(
                output="\n".join(b.text for b in response.content if hasattr(b, "text")),
                trace=trace,
            )

        # Process tool calls
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue

            tool_name: str = block.name
            tool_inputs: dict[str, Any] = block.input  # type: ignore[assignment]

            trace.append(TraceEvent.tool_call(tool_name, tool_inputs))

            handler = _TOOL_HANDLERS.get(tool_name)
            if handler is None:
                result = {"error": f"unknown tool: {tool_name}"}
                trace.append(TraceEvent.tool_result(tool_name, None, error=result["error"]))
            else:
                result = handler(tool_inputs)
                trace.append(TraceEvent.tool_result(tool_name, result))

            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                }
            )

        # Append assistant turn + tool results and loop
        messages.append({"role": "assistant", "content": response.content})  # type: ignore[arg-type]
        messages.append({"role": "user", "content": tool_results})


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python agent.py '<customer message>'")
        sys.exit(1)

    user_input = " ".join(sys.argv[1:])
    print(f"Input: {user_input}\n")

    # When run as a script, sys.path may not include the api package.
    # Add the src directory so the api package is importable.
    import pathlib

    src_dir = pathlib.Path(__file__).parents[2] / "apps" / "api" / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    result = run(user_input)
    print(f"Output:\n{result.output}\n")
    print(f"Trace ({len(result.trace)} events):")
    for event in result.trace:
        print(f"  [{event.type}] {event.data}")
