"""
properties/ai/__init__.py

Public API of the ai package.
Import everything views.py needs from here — internal structure can change freely.
"""

from properties.ai.constants import MAX_CHAT_HISTORY, MAX_LIMIT
from properties.ai.groq_client import (
    call_groq,
    call_groq_chat,
    call_groq_prompt,
    groq_completion,
    is_groq_configured,
)
from properties.ai.parser import parse_ai_response
from properties.ai.filters import apply_filters
from properties.ai.comparison import (
    detect_intent,
    serialize_property_for_comparison,
    build_comparison_prompt,
)

__all__ = [
    # constants
    "MAX_CHAT_HISTORY",
    "MAX_LIMIT",
    # groq client
    "call_groq",
    "call_groq_chat",
    "call_groq_prompt",
    "groq_completion",
    "is_groq_configured",
    # parser
    "parse_ai_response",
    # filters
    "apply_filters",
    # comparison
    "detect_intent",
    "serialize_property_for_comparison",
    "build_comparison_prompt",
]