"""
constants.py — Shared constants for the AI chat service.

Hard caps protect against hallucinated large values and abuse.
Centralised here so validators, parser, and views all share the same values.
"""

# Hard caps (security / hallucination guard)
MAX_CONDITIONS  = 10
MAX_SORTS       = 3
MAX_LIMIT       = 50
MAX_CHAT_HISTORY = 20

# Fields that require numeric values
NUMERIC_FIELDS = {"price", "area", "rooms", "bedrooms", "bathrooms"}