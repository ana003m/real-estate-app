import json
import re
import os
from django.db.models import Q
from decouple import config
from groq import Groq

# ============================================================================
# CONFIGURATION
# ============================================================================

GROQ_API_KEY = config("GROQ_API_KEY", default=os.getenv("GROQ_API_KEY", "")).strip()
GROQ_MODEL = config("GROQ_MODEL", default="llama-3.3-70b-versatile").strip() or "llama-3.3-70b-versatile"

# Maximum number of messages to keep in chat history
MAX_CHAT_HISTORY = 10

# ============================================================================
# SYSTEM PROMPT FOR GROQ
# ============================================================================

SYSTEM_PROMPT = """
You are a real estate assistant. Convert the user's message into structured JSON.

Choose one of two modes:

--- MODE: filter ---
Use when the user wants to find, browse, or sort properties.
{
  "mode": "filter",
  "conditions": [
    {"field": "...", "op": "...", "value": ...}
  ],
  "sort": [
    {"field": "...", "direction": "asc" | "desc"}
  ],
  "limit": null,
  "message": "One sentence summary of the search."
}

FIELDS: price, area, rooms, bedrooms, bathrooms, city, location, property_type, listing_type, features
OPS: eq, lt, lte, gt, gte, icontains
SORT fields: price, area, rooms, bedrooms, bathrooms, created_at

Rules:
- "highest price" / "most expensive" → sort: [{"field":"price","direction":"desc"}]
- "lowest price" / "cheapest" → sort: [{"field":"price","direction":"asc"}]
- "less than X bedrooms" → {"field":"bedrooms","op":"lt","value":X}
- "more than X bedrooms" / "at least X bedrooms" → {"field":"bedrooms","op":"gte","value":X}
- "under $X" / "below $X" / "max $X" → {"field":"price","op":"lte","value":X}
- "over $X" / "above $X" / "at least $X" → {"field":"price","op":"gte","value":X}
- "apartments" / "apartment" → {"field":"property_type","op":"eq","value":"apartment"}
- "houses" / "house" → {"field":"property_type","op":"eq","value":"house"}
- "villas" / "villa" → {"field":"property_type","op":"eq","value":"villa"}
- "studios" / "studio" → {"field":"property_type","op":"eq","value":"studio"}
- "land" → {"field":"property_type","op":"eq","value":"land"}
- "commercial" → {"field":"property_type","op":"eq","value":"commercial"}
- "for rent" / "to rent" → {"field":"listing_type","op":"eq","value":"rent"}
- "for sale" / "to buy" → {"field":"listing_type","op":"eq","value":"sale"}
- "in Chicago" → {"field":"city","op":"icontains","value":"Chicago"}
- "not in Chicago" / "outside Chicago" / "excluding Chicago" → {"field":"city","op":"not_icontains","value":"Chicago"}
- "not apartments" / "excluding apartments" → {"field":"property_type","op":"neq","value":"apartment"}
- "not for rent" / "excluding rentals" → {"field":"listing_type","op":"neq","value":"rent"}
- "apartments or houses" → {"field":"property_type","op":"in","value":["apartment","house"]}
- "for rent or for sale" → {"field":"listing_type","op":"in","value":["rent","sale"]}
- "with pool" → {"field":"features","op":"icontains","value":"pool"}
- "with pool AND garage" (both required) → two separate conditions: {"field":"features","op":"icontains","value":"pool"} AND {"field":"features","op":"icontains","value":"garage"}
- "with pool OR garage" (either is enough) → {"field":"features","op":"any_of","value":["pool","garage"]}
- "without pool" / "no pool" / "excluding pool" → {"field":"features","op":"none_of","value":["pool"]}
- "without pool or garage" / "no pool and no garage" → {"field":"features","op":"none_of","value":["pool","garage"]}
- "biggest" / "largest" → sort: [{"field":"area","direction":"desc"}]
- "smallest" → sort: [{"field":"area","direction":"asc"}]
- "newest" / "latest" → sort: [{"field":"created_at","direction":"desc"}]
- "more than X rooms" → {"field":"rooms","op":"gt","value":X}
- "most bathrooms" / "most bedrooms" / "most rooms" → sort by that field desc
- "one property" / "only one" / "show me one" / "top 1" → limit: 1
- "property with most X" → limit: 1 (e.g. "property with most bathrooms" → limit:1, sort bathrooms desc)
- "property with highest X" → limit: 1 (e.g. "property with highest price" → limit:1, sort price desc)
- "property with lowest X" → limit: 1 (e.g. "property with lowest price" → limit:1, sort price asc)
- "cheapest property" / "most expensive property" → limit: 1
- "biggest property" / "largest property" / "smallest property" → limit: 1
- "newest property" / "oldest property" → limit: 1
- plural "properties" → do NOT set limit (leave null)
- "top X" / "show me X" / "X properties" (where X is a small number like 2,3,4,5) → limit: X
- Each user message is a FRESH, independent search. Do NOT carry over conditions from previous messages.
- Use empty arrays [] if no filter or sort criteria are mentioned.
- Use null for limit when no specific count is requested.

--- MODE: aggregate ---
Use when the user asks for a statistic across multiple properties (average, total, minimum, maximum, count).
{
  "mode": "aggregate",
  "conditions": [...],
  "operation": "avg" | "min" | "max" | "sum" | "count",
  "field": "price" | "area" | "bedrooms" | "bathrooms" | "rooms"
}

Examples:
- "average price of houses" → conditions: [property_type=house], operation: "avg", field: "price"
- "how many villas are there?" → conditions: [property_type=villa], operation: "count", field: "price"
- "total value of all properties" → conditions: [], operation: "sum", field: "price"
- "maximum area among apartments" → conditions: [property_type=apartment], operation: "max", field: "area"
- "minimum price in Chicago" → conditions: [city=Chicago], operation: "min", field: "price"

--- MODE: question ---
Use when the user asks a specific factual question about a particular property
(e.g. "how many features does X have?", "what is the area of Y?", "does Z have a pool?", "how many rooms does the house in Chicago have?").
{
  "mode": "question",
  "conditions": [...],
  "sort": [...],
  "attribute": "features" | "area" | "bedrooms" | "bathrooms" | "rooms" | "price" | "location" | "general"
}
Use sort to identify the right property when the user says "most expensive", "cheapest", "biggest", etc.
Example: "how many bathrooms does the most expensive villa have?" →
  conditions: [{"field":"property_type","op":"eq","value":"villa"}], sort: [{"field":"price","direction":"desc"}], attribute: "bathrooms"

attribute values:
- "features" → user asks about features (count, list, or whether it has a specific one)
- "area" → user asks about size/area
- "bedrooms" → user asks about bedrooms
- "bathrooms" → user asks about bathrooms
- "rooms" → user asks about rooms
- "price" → user asks about price
- "location" → user asks about address/city/location
- "general" → any other factual question about the property

--- MODE: chat ---
Use for greetings, general real estate questions, advice, or anything NOT a property search or specific property question.
{
  "mode": "chat",
  "message": "Your helpful, conversational response here."
}

Return ONLY valid JSON. No markdown, no extra text.
"""

# Comparison system prompt for property comparisons
COMPARISON_SYSTEM_PROMPT = """You are a helpful real estate assistant.
Compare the properties using exactly this format:

**[Property 1 name] vs [Property 2 name]**

• **Price:** $X vs $Y
• **Price/m²:** $X vs $Y
• **Size:** Xm² vs Ym²
• **Beds/Baths:** X bed X bath vs Y bed Y bath
• **Location:** City1 vs City2

**Verdict:** One sentence saying which is the better deal and why.

Only use the provided data. No extra lines or commentary."""

# ============================================================================
# ALLOWED VALUES FOR VALIDATION
# ============================================================================

ALLOWED_FIELDS = {
    "price", "area", "rooms", "bedrooms", "bathrooms",
    "city", "location", "property_type", "listing_type", "features",
}
ALLOWED_OPS = {"eq", "lt", "lte", "gt", "gte", "icontains", "any_of", "neq", "not_icontains", "in", "none_of"}
ALLOWED_SORT_FIELDS = {"price", "area", "rooms", "bedrooms", "bathrooms", "created_at"}
ALLOWED_DIRECTIONS = {"asc", "desc"}

FIELD_LOOKUPS = {
    "eq": "",
    "lt": "__lt",
    "lte": "__lte",
    "gt": "__gt",
    "gte": "__gte",
    "icontains": "__icontains",
}

NUMERIC_FIELDS = {"price", "area", "rooms", "bedrooms", "bathrooms"}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def build_prompt(chat_history):
    """Build a prompt from chat history for single-turn requests"""
    conversation = "\n".join(
        f"{msg.get('role', 'user').upper()}: {msg.get('content', '')}"
        for msg in chat_history
    )
    return f"{SYSTEM_PROMPT}\n\nConversation:\n{conversation}\n\nJSON:"


def is_groq_configured():
    """Check if GROQ API key is configured"""
    return bool(GROQ_API_KEY)


def get_groq_client():
    """Get GROQ client instance, raise error if API key missing"""
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is missing. Add it to .env and restart the server.")
    return Groq(api_key=GROQ_API_KEY)


def call_groq_prompt(prompt):
    """Single-turn prompt call - used for description generation and property comparison"""
    client = get_groq_client()
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


def call_groq(chat_history):
    """Call GROQ with conversation history for intent parsing"""
    client = get_groq_client()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in chat_history:
        role = msg.get("role", "user")
        if role in ("user", "assistant"):
            messages.append({"role": role, "content": msg.get("content", "")})
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0,
    )
    return response.choices[0].message.content.strip()


def call_groq_chat(user_message):
    """Simple chat call without JSON formatting"""
    client = get_groq_client()
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system",
             "content": "You are a helpful real estate assistant. Answer the user's question naturally and concisely."},
            {"role": "user", "content": user_message},
        ],
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


def safe_num(value):
    """Safely convert a value to number (int or float)"""
    try:
        if value is None:
            return None
        s = str(value).replace(",", "").strip()
        f = float(s)
        return int(f) if f == int(f) else f
    except Exception:
        return None


def normalize_property_name(name):
    """
    Normalize property names for fuzzy comparison.
    Example: 'Luxury Villa #5' -> 'luxury villa 5'
    Removes special characters and converts to lowercase
    """
    normalized = re.sub(r'[^a-zA-Z0-9\s]', ' ', name)  # Replace special chars with space
    normalized = re.sub(r'\s+', ' ', normalized)  # Collapse multiple spaces
    return normalized.strip().lower()


# ============================================================================
# CONDITION AND SORT VALIDATION
# ============================================================================

def validate_condition(cond):
    """
    Validate and normalize a filter condition.
    Returns normalized condition dict or None if invalid.
    Raises ValueError for specific operator/field mismatches.
    """
    if not isinstance(cond, dict):
        return None

    field = cond.get("field")
    op = cond.get("op", "eq")
    value = cond.get("value")

    # Check if field and operator are allowed
    if field not in ALLOWED_FIELDS or op not in ALLOWED_OPS or value is None:
        return None

    # Special validation for any_of and none_of operators
    if op in ("any_of", "none_of"):
        if field != "features":
            # Explicit error instead of silently dropping the condition
            raise ValueError(f"Operator '{op}' is only allowed for 'features' field, not '{field}'")

        if not isinstance(value, list) or not value:
            raise ValueError(f"Operator '{op}' requires a non-empty list value")

        return {"field": field, "op": op, "value": [str(v).lower() for v in value]}

    # Handle 'in' operator
    if op == "in":
        if not isinstance(value, list) or not value:
            return None
        if field in NUMERIC_FIELDS:
            value = [safe_num(v) for v in value]
            if any(v is None for v in value):
                return None
        return {"field": field, "op": op, "value": value}

    # Auto-convert eq to icontains for text fields
    if field in ("city", "location") and op == "eq":
        op = "icontains"

    # Convert numeric values
    if field in NUMERIC_FIELDS:
        value = safe_num(value)
        if value is None:
            return None

    return {"field": field, "op": op, "value": value}


def validate_sort(s):
    """Validate a sort directive"""
    if not isinstance(s, dict):
        return None
    field = s.get("field")
    direction = s.get("direction", "asc")
    if field not in ALLOWED_SORT_FIELDS or direction not in ALLOWED_DIRECTIONS:
        return None
    return {"field": field, "direction": direction}


# ============================================================================
# MESSAGE BUILDING FROM CONDITIONS
# ============================================================================

def build_message_from_conditions(conditions, sort):
    """
    Generate a human-readable message from filter conditions and sort directives.
    Handles all operator types including neq, not_icontains, in, any_of, none_of.
    """
    if not conditions:
        message = "All properties"
    else:
        parts = []

        for cond in conditions:
            field = cond.get("field")
            op = cond.get("op")
            value = cond.get("value")

            # Property type handling
            if field == "property_type":
                if op == "neq":
                    parts.append(f"excluding {value}s")
                elif op == "in":
                    types = " or ".join(str(v).capitalize() + "s" for v in value)
                    parts.append(types)
                else:  # eq
                    parts.append(str(value).capitalize() + "s")

            # Listing type handling
            elif field == "listing_type":
                if op == "neq":
                    excluded = "rent" if value == "rent" else "sale"
                    parts.append(f"excluding {excluded}")
                else:
                    parts.append("for rent" if value == "rent" else "for sale")

            # City/Location handling
            elif field == "city" or field == "location":
                if op == "neq" or op == "not_icontains":
                    parts.append(f"not in {value}")
                elif op == "in":
                    parts.append(f"in {', '.join(value)}")
                else:
                    parts.append(f"in {value}")

            # Price handling
            elif field == "price":
                if op == "lte" or op == "lt":
                    parts.append(f"under ${int(value):,}")
                elif op == "gte" or op == "gt":
                    parts.append(f"over ${int(value):,}")
                elif op == "eq":
                    parts.append(f"at ${int(value):,}")
                elif op == "neq":
                    parts.append(f"not priced at ${int(value):,}")
                elif op == "in":
                    prices = [f"${int(v):,}" for v in value]
                    parts.append(f"priced at {' or '.join(prices)}")

            # Numeric fields (bedrooms, bathrooms, rooms)
            elif field in ("bedrooms", "bathrooms", "rooms"):
                label = field
                if op == "gte" or op == "gt":
                    parts.append(f"with {value}+ {label}")
                elif op == "lte" or op == "lt":
                    parts.append(f"with fewer than {value} {label}")
                elif op == "eq":
                    parts.append(f"with {value} {label}")
                elif op == "neq":
                    parts.append(f"without {value} {label}")
                elif op == "in":
                    parts.append(f"with {', '.join(str(v) for v in value)} {label}")

            # Area handling
            elif field == "area":
                if op == "gte" or op == "gt":
                    parts.append(f"over {value}m²")
                elif op == "lte" or op == "lt":
                    parts.append(f"under {value}m²")
                elif op == "eq":
                    parts.append(f"exactly {value}m²")
                elif op == "neq":
                    parts.append(f"not {value}m²")

            # Features handling (supports any_of, none_of, icontains, neq, in)
            elif field == "features":
                if op == "any_of":
                    parts.append(f"with any of: {', '.join(value)}")
                elif op == "none_of":
                    parts.append(f"without: {', '.join(value)}")
                elif op == "neq":
                    parts.append(f"without {value}")
                elif op == "icontains":
                    parts.append(f"with {value}")
                elif op == "in":
                    parts.append(f"with features: {', '.join(value)}")

            # Generic handling for other operators
            else:
                if op == "neq":
                    parts.append(f"where {field} is not {value}")
                elif op == "not_icontains":
                    parts.append(f"excluding '{value}' from {field}")
                elif op == "in":
                    parts.append(f"where {field} is in ({', '.join(str(v) for v in value)})")
                elif op == "icontains":
                    parts.append(f"with {field} containing '{value}'")

        # Build the final message
        if parts:
            # Check if first part is a property type (starts with capital letter and ends with 's')
            if parts[0] and parts[0][0].isupper() and parts[0][-1] == 's':
                message = " ".join(parts)
            else:
                message = "Properties " + " ".join(parts)
        else:
            message = "Properties"

    # Add sorting information
    if sort:
        sort_parts = []
        for s in sort:
            direction = "highest" if s["direction"] == "desc" else "lowest"
            sort_parts.append(f"{direction} {s['field']}")

        if sort_parts:
            message += " sorted by " + ", ".join(sort_parts)

    return message + "."


# ============================================================================
# PARSE AI RESPONSE
# ============================================================================

def parse_ai_response(raw):
    """
    Parse and validate the JSON response from GROQ.
    Handles different modes: filter, aggregate, question, chat.
    """
    text = raw.strip()

    # Remove markdown code blocks if present
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                text = part
                break

    # Extract JSON object
    start = text.find("{")
    end = text.rfind("}") + 1

    if start == -1 or end == 0:
        raise ValueError("No JSON found")

    parsed = json.loads(text[start:end])
    mode = parsed.get("mode", "filter")

    # Handle chat mode
    if mode == "chat":
        return {
            "mode": "chat",
            "message": parsed.get("message", "How can I help you?"),
            "conditions": [],
            "sort": [],
        }

    # Handle aggregate mode
    if mode == "aggregate":
        raw_conditions = parsed.get("conditions", [])
        conditions = [c for c in (validate_condition(c) for c in raw_conditions) if c]
        if raw_conditions and not conditions:
            return {
                "mode": "chat",
                "message": "I couldn't understand the requested filters. Try rephrasing your search.",
                "conditions": [],
                "sort": [],
            }
        allowed_ops = {"avg", "min", "max", "sum", "count"}
        allowed_fields = {"price", "area", "bedrooms", "bathrooms", "rooms"}
        operation = parsed.get("operation", "avg")
        agg_field = parsed.get("field", "price")
        if operation not in allowed_ops:
            operation = "avg"
        if agg_field not in allowed_fields:
            agg_field = "price"
        return {
            "mode": "aggregate",
            "conditions": conditions,
            "operation": operation,
            "agg_field": agg_field,
            "sort": [],
            "limit": None,
            "message": "",
        }

    # Handle question mode
    if mode == "question":
        raw_conditions = parsed.get("conditions", [])
        raw_sort = parsed.get("sort", [])
        conditions = [c for c in (validate_condition(c) for c in raw_conditions) if c]
        sort = [s for s in (validate_sort(s) for s in raw_sort) if s]
        if raw_conditions and not conditions:
            return {
                "mode": "chat",
                "message": "I couldn't understand the requested filters. Try rephrasing your search.",
                "conditions": [],
                "sort": [],
            }
        allowed_attrs = {"features", "area", "bedrooms", "bathrooms", "rooms", "price", "location", "general"}
        attribute = parsed.get("attribute", "general")
        if attribute not in allowed_attrs:
            attribute = "general"
        return {
            "mode": "question",
            "conditions": conditions,
            "attribute": attribute,
            "sort": sort,
            "limit": 1,  # Questions always target a single property
            "message": "",
        }

    # Handle filter mode (default)
    raw_conditions = parsed.get("conditions", [])
    raw_sort = parsed.get("sort", [])

    conditions = [c for c in (validate_condition(c) for c in raw_conditions) if c]
    sort = [s for s in (validate_sort(s) for s in raw_sort) if s]

    # IMPORTANT: limit: null means NO limit (show all properties)
    raw_limit = parsed.get("limit")
    if raw_limit is None:
        limit = None  # None means "show all" - no limit
    elif isinstance(raw_limit, (int, float)) and raw_limit > 0:
        limit = int(raw_limit)
    else:
        limit = None  # Invalid limit also means no limit

    # Generate message if not provided
    message = parsed.get("message")
    if not message:
        message = build_message_from_conditions(conditions, sort)

    return {
        "mode": "filter",
        "conditions": conditions,
        "sort": sort,
        "limit": limit,
        "message": message,
    }


# ============================================================================
# APPLY FILTERS TO QUERYSET
# ============================================================================

def apply_filters(queryset, parsed):
    """
    Apply conditions and sorting to a Django queryset.
    Handles special operators: any_of, none_of, neq, not_icontains, in.
    """
    conditions = parsed.get("conditions", [])
    sort = parsed.get("sort", [])

    for cond in conditions:
        field = cond["field"]
        op = cond["op"]
        value = cond["value"]

        # Handle features with any_of (OR logic)
        if field == "features" and op == "any_of":
            q = Q()
            for v in value:
                q |= Q(features__name__icontains=v) | Q(custom_features__icontains=v)
            queryset = queryset.filter(q).distinct()
            continue

        # Handle features with none_of (exclude all specified)
        if field == "features" and op == "none_of":
            for v in value:
                queryset = queryset.exclude(
                    Q(features__name__icontains=v) | Q(custom_features__icontains=v)
                )
            queryset = queryset.distinct()
            continue

        # Handle regular features icontains
        if field == "features":
            queryset = queryset.filter(
                Q(features__name__icontains=value) |
                Q(custom_features__icontains=value)
            ).distinct()
            continue

        # Handle not equal operator
        if op == "neq":
            queryset = queryset.exclude(**{field: value})
            continue

        # Handle not contains (text fields)
        if op == "not_icontains":
            queryset = queryset.exclude(**{f"{field}__icontains": value})
            continue

        # Handle IN operator
        if op == "in":
            queryset = queryset.filter(**{f"{field}__in": value})
            continue

        # Standard lookups
        suffix = FIELD_LOOKUPS.get(op, "")
        lookup = f"{field}{suffix}" if suffix else field
        queryset = queryset.filter(**{lookup: value})

    # Apply sorting
    if sort:
        order_fields = []
        for s in sort:
            prefix = "-" if s["direction"] == "desc" else ""
            order_fields.append(f"{prefix}{s['field']}")
        queryset = queryset.order_by(*order_fields)

    return queryset


# ============================================================================
# PROPERTY COMPARISON FUNCTIONS
# ============================================================================

def serialize_property_for_comparison(prop):
    """Serialize a property object for comparison display"""
    features = list(prop.features.values_list('name', flat=True))
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


def build_comparison_prompt(props_data, chat_history):
    """Build a prompt for comparing multiple properties"""
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


def detect_intent(message, queryset):
    """
    Detect if user wants to compare properties.
    Uses fuzzy matching for property names.
    Returns (intent_type, list_of_properties)
    intent_type can be "compare" or "filter"
    """
    found = []
    seen_ids = set()

    # Normalize the user's message for fuzzy matching
    normalized_message = normalize_property_name(message)

    # Detect property IDs in the message (e.g., #123, property 456)
    id_matches = re.findall(
        r'(?:#|(?:property|id|listing)\s+)(\d+)',
        message,
        re.IGNORECASE,
    )

    for id_str in id_matches:
        try:
            prop = queryset.filter(id=int(id_str)).first()
            if prop and prop.id not in seen_ids:
                found.append(prop)
                seen_ids.add(prop.id)
        except (ValueError, TypeError):
            pass

    # Fuzzy name matching - look for normalized property names in message
    if len(found) < 2:
        for prop in queryset:
            if prop.id in seen_ids or len(prop.name) < 3:
                continue

            normalized_name = normalize_property_name(prop.name)

            # Check if normalized name appears in normalized message
            if normalized_name in normalized_message:
                found.append(prop)
                seen_ids.add(prop.id)

            if len(found) >= 4:
                break

    # If still not enough matches, try word intersection
    if len(found) < 2:
        for prop in queryset:
            if prop.id in seen_ids:
                continue

            # Extract meaningful words from property name (min 3 chars, letters only)
            name_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', prop.name.lower()))
            msg_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', message.lower()))

            # If at least 2 words match, consider it a match
            if len(name_words.intersection(msg_words)) >= 2:
                found.append(prop)
                seen_ids.add(prop.id)

            if len(found) >= 4:
                break

    # Return comparison mode if we found at least 2 properties
    if len(found) >= 2:
        return ("compare", found[:4])  # Limit to 4 properties for comparison

    return ("filter", [])