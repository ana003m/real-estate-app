"""
filters.py — Django queryset filtering.

Builds include_q and exclude_q objects, then applies them in a
single .filter() / .exclude() call for clean, performant queries.
"""

from django.db.models import Q

from properties.ai.validators import OPERATOR_REGISTRY


def apply_filters(queryset, parsed):
    """
    Apply conditions and sort from a parsed AI response to a queryset.

    Args:
        queryset: base Property queryset (already filtered by status=approved)
        parsed:   dict with keys "conditions" and "sort"

    Returns:
        Filtered (and optionally sorted) queryset.
    """
    conditions = parsed.get("conditions", [])
    sort = parsed.get("sort", [])

    include_q = Q()
    exclude_q = Q()
    needs_distinct = False

    for cond in conditions:
        field = cond["field"]
        op = cond["op"]
        value = cond["value"]

        # --- features (ManyToMany + custom_features TextField) ---
        if field == "features":
            needs_distinct = True
            if op == "any_of":
                q = Q()
                for v in value:
                    q |= Q(features__name__icontains=v) | Q(custom_features__icontains=v)
                include_q &= q
            elif op == "none_of":
                for v in value:
                    exclude_q |= (
                        Q(features__name__icontains=v) | Q(custom_features__icontains=v)
                    )
            else:  # icontains / eq
                include_q &= (
                    Q(features__name__icontains=value) | Q(custom_features__icontains=value)
                )
            continue

        # --- special operators ---
        if op == "neq":
            exclude_q |= Q(**{field: value})
            continue

        if op == "not_icontains":
            exclude_q |= Q(**{f"{field}__icontains": value})
            continue

        if op == "in":
            include_q &= Q(**{f"{field}__in": value})
            continue

        # --- standard operators (eq, lt, lte, gt, gte, icontains) ---
        suffix = OPERATOR_REGISTRY.get(op, "")
        lookup = f"{field}{suffix}" if suffix else field
        include_q &= Q(**{lookup: value})

    # Apply filters in one pass
    if include_q != Q():
        queryset = queryset.filter(include_q)
    if exclude_q != Q():
        queryset = queryset.exclude(exclude_q)
    if needs_distinct:
        queryset = queryset.distinct()

    # Ordering
    if sort:
        order_fields = [
            f"{'-' if s['direction'] == 'desc' else ''}{s['field']}"
            for s in sort
        ]
        queryset = queryset.order_by(*order_fields)

    return queryset