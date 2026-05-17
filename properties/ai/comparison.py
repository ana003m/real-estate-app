"""
comparison.py — Property comparison logic.

Responsibilities:
  - _normalize()                      — fuzzy name normalisation
  - detect_intent()                   — compare vs filter decision
  - serialize_property_for_comparison() — property → dict for prompt
  - build_comparison_prompt()         — assembles the Groq prompt
"""

import re

from properties.ai.prompts import COMPARISON_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize(text):
    """Strip punctuation and collapse whitespace for fuzzy name matching."""
    return re.sub(r"[\s#\-_]+", " ", text).strip().lower()


# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------

def detect_intent(message, queryset):
    """
    Decide whether the user wants to compare specific properties or filter.

    Returns:
        ("compare", [prop, ...])  if 2–4 named properties are found
        ("filter",  [])           otherwise
    """
    found = []
    seen_ids = set()

    # 1. Match explicit IDs: "#101", "property 101", "listing 101"
    id_matches = re.findall(
        r"(?:#|(?:property|id|listing)\s+)(\d+)", message, re.IGNORECASE
    )
    for id_str in id_matches:
        try:
            prop = queryset.filter(id=int(id_str)).first()
            if prop and prop.id not in seen_ids:
                found.append(prop)
                seen_ids.add(prop.id)
        except (ValueError, TypeError):
            pass

    # 2. Match property names (normalised to handle "#", extra spaces, etc.)
    if len(found) < 2:
        norm_message = _normalize(message)
        for prop in queryset:
            if prop.id in seen_ids or len(prop.name) < 4:
                continue
            if re.search(r"\b" + re.escape(prop.name) + r"\b", message, re.IGNORECASE):
                found.append(prop)
                seen_ids.add(prop.id)
            elif _normalize(prop.name) in norm_message:
                found.append(prop)
                seen_ids.add(prop.id)
            if len(found) >= 4:
                break

    if len(found) >= 2:
        return ("compare", found[:4])
    return ("filter", [])


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def serialize_property_for_comparison(prop):
    """Convert a Property instance to a plain dict for the comparison prompt."""
    features = list(prop.features.values_list("name", flat=True))
    price_per_m2 = (
        round(float(prop.price) / float(prop.area), 2) if prop.area else None
    )
    return {
        "id": prop.id,
        "name": prop.name,
        "city": prop.city,
        "location": prop.location,
        "price": float(prop.price),
        "area": float(prop.area),
        "price_per_m2": price_per_m2,
        "property_type": prop.get_property_type_display(),
        "listing_type": prop.get_listing_type_display(),
        "bedrooms": prop.bedrooms,
        "bathrooms": prop.bathrooms,
        "rooms": prop.rooms,
        "features": features,
        "custom_features": prop.custom_features or "",
    }


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_comparison_prompt(props_data, chat_history):
    """Build the Groq prompt for a multi-property comparison."""
    props_text = "\n\n".join(
        "Property {n}: {name} (ID: {id})\n"
        "  City: {city}, Location: {location}\n"
        "  Price: ${price:,.0f} ({listing_type})\n"
        "  Price per m²: ${price_per_m2}\n"
        "  Type: {property_type}, Area: {area} m²\n"
        "  Bedrooms: {bedrooms}, Bathrooms: {bathrooms}\n"
        "  Features: {features}\n"
        "  Additional: {custom_features}".format(
            n=i + 1,
            features=", ".join(p["features"]) or "None",
            **{k: v for k, v in p.items() if k != "features"},
        )
        for i, p in enumerate(props_data)
    )
    last_user_msg = next(
        (m["content"] for m in reversed(chat_history) if m["role"] == "user"),
        "Which is better?",
    )
    return (
        f"{COMPARISON_SYSTEM_PROMPT}\n\n"
        f"Properties:\n{props_text}\n\n"
        f"User question: {last_user_msg}\n\nYour comparison:"
    )