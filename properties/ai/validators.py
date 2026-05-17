"""
validators.py — Condition and sort validation.

Responsibilities:
  - ALLOWED_* sets (whitelist for fields, ops, sort fields)
  - OPERATOR_REGISTRY (op → Django ORM lookup suffix)
  - safe_num()         — safe numeric coercion
  - _normalize_value() — per-op value coercion
  - validate_condition() — returns clean dict or None
  - validate_sort()      — returns clean dict or None
"""

from properties.ai.constants import MAX_CONDITIONS, MAX_SORTS, NUMERIC_FIELDS

# ---------------------------------------------------------------------------
# Whitelists
# ---------------------------------------------------------------------------

ALLOWED_FIELDS = {
    "price", "area", "rooms", "bedrooms", "bathrooms",
    "city", "location", "property_type", "listing_type", "features",
}

ALLOWED_OPS = {
    "eq", "lt", "lte", "gt", "gte",
    "icontains", "neq", "not_icontains", "in", "any_of", "none_of",
}

ALLOWED_SORT_FIELDS = {"price", "area", "rooms", "bedrooms", "bathrooms", "created_at"}
ALLOWED_DIRECTIONS = {"asc", "desc"}

# op → Django ORM suffix (neq / not_icontains / in / any_of / none_of handled in filters.py)
OPERATOR_REGISTRY = {
    "eq":        "",
    "lt":        "__lt",
    "lte":       "__lte",
    "gt":        "__gt",
    "gte":       "__gte",
    "icontains": "__icontains",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def safe_num(value):
    """Convert a value to int or float; return None on failure."""
    try:
        if value is None:
            return None
        f = float(str(value).replace(",", "").strip())
        return int(f) if f == int(f) else f
    except Exception:
        return None


def _normalize_value(field, op, value):
    """Coerce and normalise a condition value; return None if invalid."""
    if op in ("any_of", "none_of"):
        if field != "features" or not isinstance(value, list) or not value:
            return None
        return [str(v) for v in value]

    if op == "in":
        if not isinstance(value, list) or not value:
            return None
        if field in NUMERIC_FIELDS:
            nums = [safe_num(v) for v in value]
            if any(v is None for v in nums):
                return None
            return nums
        return value

    if field in NUMERIC_FIELDS:
        return safe_num(value)  # None propagates → condition rejected

    return value


# ---------------------------------------------------------------------------
# Public validators
# ---------------------------------------------------------------------------

def validate_condition(cond):
    """Return a clean condition dict, or None if invalid."""
    if not isinstance(cond, dict):
        return None
    field = cond.get("field")
    op = cond.get("op", "eq")
    value = cond.get("value")

    if field not in ALLOWED_FIELDS or op not in ALLOWED_OPS or value is None:
        return None

    # city/location with eq → promote to icontains
    if field in ("city", "location") and op == "eq":
        op = "icontains"

    norm_value = _normalize_value(field, op, value)
    if norm_value is None:
        return None

    return {"field": field, "op": op, "value": norm_value}


def validate_sort(s):
    """Return a clean sort dict, or None if invalid."""
    if not isinstance(s, dict):
        return None
    field = s.get("field")
    direction = s.get("direction", "asc")
    if field not in ALLOWED_SORT_FIELDS or direction not in ALLOWED_DIRECTIONS:
        return None
    return {"field": field, "direction": direction}


def parse_conditions(raw):
    """Validate and cap a list of raw condition dicts."""
    return [c for c in (validate_condition(c) for c in raw[:MAX_CONDITIONS]) if c]


def parse_sort(raw):
    """Validate and cap a list of raw sort dicts."""
    return [s for s in (validate_sort(s) for s in raw[:MAX_SORTS]) if s]