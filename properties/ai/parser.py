"""
parser.py — AI response parsing.

Responsibilities:
  - parse_ai_response()  — entry point, strips fences, loads JSON
  - MODE_HANDLERS        — dispatch table mapping mode → parser function
  - parse_chat_mode()
  - parse_aggregate_mode()
  - parse_question_mode()
  - parse_filter_mode()
"""

import json

from properties.ai.constants import MAX_LIMIT
from properties.ai.validators import parse_conditions, parse_sort
from properties.ai.utils import build_message_from_conditions


# ---------------------------------------------------------------------------
# Per-mode parsers
# ---------------------------------------------------------------------------

def parse_chat_mode(parsed):
    return {
        "mode": "chat",
        "message": parsed.get("message", "How can I help you?"),
        "conditions": [],
        "sort": [],
    }


def parse_aggregate_mode(parsed):
    allowed_ops = {"avg", "min", "max", "sum", "count"}
    allowed_agg_fields = {"price", "area", "bedrooms", "bathrooms", "rooms"}
    operation = parsed.get("operation", "avg")
    agg_field = parsed.get("field", "price")
    return {
        "mode": "aggregate",
        "conditions": parse_conditions(parsed.get("conditions", [])),
        "operation": operation if operation in allowed_ops else "avg",
        "agg_field": agg_field if agg_field in allowed_agg_fields else "price",
        "sort": [],
        "limit": None,
        "message": "",
    }


def parse_question_mode(parsed):
    allowed_attrs = {
        "features", "area", "bedrooms", "bathrooms",
        "rooms", "price", "location", "general",
    }
    attribute = parsed.get("attribute", "general")
    return {
        "mode": "question",
        "conditions": parse_conditions(parsed.get("conditions", [])),
        "attribute": attribute if attribute in allowed_attrs else "general",
        "sort": parse_sort(parsed.get("sort", [])),
        "limit": 1,
        "message": "",
    }


def parse_filter_mode(parsed):
    conditions = parse_conditions(parsed.get("conditions", []))
    sort = parse_sort(parsed.get("sort", []))

    raw_limit = parsed.get("limit")
    try:
        limit = int(raw_limit) if raw_limit is not None else None
        if limit is not None:
            limit = max(1, min(limit, MAX_LIMIT))
    except (TypeError, ValueError):
        limit = None

    message = parsed.get("message") or build_message_from_conditions(conditions, sort)
    return {
        "mode": "filter",
        "conditions": conditions,
        "sort": sort,
        "limit": limit,
        "message": message,
    }


# Dispatch table — replaces the big if/elif in parse_ai_response
MODE_HANDLERS = {
    "chat":      parse_chat_mode,
    "aggregate": parse_aggregate_mode,
    "question":  parse_question_mode,
    "filter":    parse_filter_mode,
}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_ai_response(raw):
    """Parse raw Groq JSON string → structured dict via per-mode handlers."""
    text = raw.strip()

    # Strip markdown code fences if present
    if "```" in text:
        for part in text.split("```"):
            part = part.strip().lstrip("json").strip()
            if part.startswith("{"):
                text = part
                break

    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("No JSON object found in AI response")

    parsed = json.loads(text[start:end])
    mode = parsed.get("mode", "filter")
    handler = MODE_HANDLERS.get(mode, parse_filter_mode)
    return handler(parsed)