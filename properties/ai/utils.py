"""
utils.py — Message building utilities.

build_message_from_conditions() converts validated conditions and sort
directives into a human-readable summary string, using small helper
functions instead of a large if/elif chain.
"""


# ---------------------------------------------------------------------------
# Per-field message helpers
# ---------------------------------------------------------------------------

def _msg_city(op, value):
    return f"excluding {value}" if op == "not_icontains" else f"in {value}"


def _msg_listing_type(op, value):
    if op == "neq":
        return "excluding rentals" if value == "rent" else "excluding sale listings"
    if op == "in" and isinstance(value, list):
        return " or ".join("for rent" if v == "rent" else "for sale" for v in value)
    return "for rent" if value == "rent" else "for sale"


def _msg_price(op, value):
    if op in ("lte", "lt"):
        return f"under ${int(value):,}"
    if op in ("gte", "gt"):
        return f"over ${int(value):,}"
    return None


def _msg_numeric(label, op, value):
    if op in ("gte", "gt"):
        return f"with {value}+ {label}"
    if op in ("lte", "lt"):
        return f"with fewer than {value} {label}"
    if op == "eq":
        return f"with {value} {label}"
    return None


def _msg_area(op, value):
    if op in ("gte", "gt"):
        return f"over {value}m²"
    if op in ("lte", "lt"):
        return f"under {value}m²"
    return None


def _msg_features(op, value):
    if op == "any_of" and isinstance(value, list):
        return f"with {' or '.join(value)}"
    if op == "none_of" and isinstance(value, list):
        return f"without {' or '.join(value)}"
    return f"with {value}"


def _msg_location(op, value):
    return f"not near {value}" if op == "not_icontains" else f"near {value}"


# Sort label lookup: field → (desc label, asc label)
_SORT_LABELS = {
    "price":      ("highest price first",  "lowest price first"),
    "area":       ("largest first",        "smallest first"),
    "created_at": ("newest first",         "oldest first"),
    "bedrooms":   ("most bedrooms first",  "fewest bedrooms first"),
    "bathrooms":  ("most bathrooms first", "fewest bathrooms first"),
    "rooms":      ("most rooms first",     "fewest rooms first"),
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_message_from_conditions(conditions, sort):
    """Return a human-readable summary of the current filter/sort state."""
    parts = ["Properties"]

    for cond in conditions:
        field = cond.get("field")
        op = cond.get("op")
        value = cond.get("value")

        if field == "city":
            parts.append(_msg_city(op, value))

        elif field == "property_type":
            if op == "in" and isinstance(value, list):
                parts[0] = " or ".join(str(v).capitalize() + "s" for v in value)
            elif op == "neq":
                parts.append(f"excluding {str(value).lower()}s")
            else:
                parts[0] = str(value).capitalize() + "s"

        elif field == "listing_type":
            parts.append(_msg_listing_type(op, value))

        elif field == "price":
            msg = _msg_price(op, value)
            if msg:
                parts.append(msg)

        elif field == "bedrooms":
            msg = _msg_numeric("bedrooms", op, value)
            if msg:
                parts.append(msg)

        elif field == "bathrooms":
            msg = _msg_numeric("bathrooms", op, value)
            if msg:
                parts.append(msg)

        elif field == "rooms":
            msg = _msg_numeric("rooms", op, value)
            if msg:
                parts.append(msg)

        elif field == "area":
            msg = _msg_area(op, value)
            if msg:
                parts.append(msg)

        elif field == "features":
            parts.append(_msg_features(op, value))

        elif field == "location":
            parts.append(_msg_location(op, value))

    for s in sort:
        labels = _SORT_LABELS.get(s.get("field"))
        if labels:
            parts.append(f"({labels[0] if s['direction'] == 'desc' else labels[1]})")

    return " ".join(parts) + "."