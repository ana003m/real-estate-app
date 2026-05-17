"""
groq_client.py — Groq API client.

Single entry point: groq_completion().
All other call_* helpers delegate here.
Includes exponential back-off retry on transient failures.
"""

import logging
import os
import time

from decouple import config
from groq import Groq

from properties.ai.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

GROQ_API_KEY = config("GROQ_API_KEY", default=os.getenv("GROQ_API_KEY", "")).strip()
GROQ_MODEL = (
    config("GROQ_MODEL", default="llama-3.3-70b-versatile").strip()
    or "llama-3.3-70b-versatile"
)


def is_groq_configured():
    return bool(GROQ_API_KEY)


def get_groq_client():
    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is missing. Add it to .env and restart the server."
        )
    return Groq(api_key=GROQ_API_KEY)


# ---------------------------------------------------------------------------
# Core completion with retry
# ---------------------------------------------------------------------------

def groq_completion(messages, temperature=0, json_mode=False, retries=2):
    """
    Single generic Groq completion with exponential back-off retry.

    Args:
        messages:    list of {"role": ..., "content": ...}
        temperature: 0 for deterministic, 0.7 for creative
        json_mode:   True → request response_format json_object
        retries:     number of retry attempts on transient failure
    """
    client = get_groq_client()
    kwargs = dict(model=GROQ_MODEL, messages=messages, temperature=temperature)
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    last_exc = None
    for attempt in range(retries + 1):
        try:
            response = client.chat.completions.create(**kwargs)
            return response.choices[0].message.content.strip()
        except Exception as exc:
            last_exc = exc
            logger.warning("Groq API attempt %d failed: %s", attempt + 1, exc)
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))

    logger.exception("Groq API failed after %d attempts", retries + 1)
    raise last_exc


# ---------------------------------------------------------------------------
# Named call helpers (kept for readability at call sites)
# ---------------------------------------------------------------------------

def call_groq(chat_history):
    """Structured chat → JSON response for filter/aggregate/question/chat."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in chat_history:
        role = msg.get("role", "user")
        if role in ("user", "assistant"):
            messages.append({"role": role, "content": msg.get("content", "")})
    return groq_completion(messages, temperature=0, json_mode=True)


def call_groq_prompt(prompt):
    """Single-turn prompt — description generation and comparison."""
    return groq_completion(
        [{"role": "user", "content": prompt}],
        temperature=0.7,
    )


def call_groq_chat(user_message):
    """Free-form conversational reply."""
    return groq_completion(
        [
            {
                "role": "system",
                "content": (
                    "You are a helpful real estate assistant. "
                    "Answer the user's question naturally and concisely."
                ),
            },
            {"role": "user", "content": user_message},
        ],
        temperature=0.7,
    )