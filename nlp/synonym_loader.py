from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Set


def _unique_lower(values: Iterable[str]) -> List[str]:
    seen: Set[str] = set()
    ordered: List[str] = []
    for val in values:
        if not val:
            continue
        key = str(val).strip()
        if not key:
            continue
        lower = key.lower()
        if lower in seen:
            continue
        seen.add(lower)
        ordered.append(key)
    return ordered


def _collect_values(collection, fallback: List[str]) -> List[str]:
    values: List[str] = []
    try:
        if collection is not None:
            values = [v for v in collection.distinct("value") if v]
            # If the collection stores labels instead of value, fall back to label
            if not values:
                values = [v for v in collection.distinct("label") if v]
    except Exception:
        values = []
    if not values:
        values = fallback or []
    return _unique_lower(values)


def _pluralize(token: str) -> Optional[str]:
    if not token:
        return None
    if token.endswith("s"):
        return None
    if token.endswith("y") and len(token) > 1 and token[-2] not in "aeiou":
        return token[:-1] + "ies"
    return token + "s"


def _build_value_synonyms(values: List[str]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for raw in values:
        canonical = raw.strip()
        if not canonical:
            continue
        key = canonical.lower()
        variants: Set[str] = set()
        variants.add(canonical)
        variants.add(key)
        variants.add(key.replace("_", " "))
        variants.add(canonical.replace("_", " "))
        variants.add(key.replace("-", " "))
        variants.add(canonical.replace("-", " "))
        plural = _pluralize(key)
        if plural:
            variants.add(plural)
        variants.discard(key)
        variants.discard(canonical.lower())
        # Remove empties and exact canonical duplicates
        cleaned = sorted({v.strip() for v in variants if v and v.strip() and v.strip().lower() != key})
        out[key] = cleaned
    return out


def load_dynamic_synonyms(adapter: Any, static_synonyms: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Build a synonym dictionary from live Mongo data (users, options collections).
    Expects a DemoAdapter-like object with *_option_* collections and _users.
    """
    static_value_syn = (static_synonyms or {}).get("value_synonyms", {})
    static_employee_names = (static_synonyms or {}).get("employee_names", [])

    def fallback_vals(category: str) -> List[str]:
        return list(static_value_syn.get(category, {}).keys())

    # Collections (optional, guarded)
    users = getattr(adapter, "_users", None)
    locations = getattr(adapter, "_option_locations", None)
    roles = getattr(adapter, "_option_roles", None)
    employment_types = getattr(adapter, "_option_employment_types", None)
    managers = getattr(adapter, "_option_managers", None)
    directory_groups = getattr(adapter, "_option_groups", None)
    departments = getattr(adapter, "_option_departments", None)

    dynamic: Dict[str, Any] = {"value_synonyms": {}, "employee_names": []}

    # Employee names
    try:
        names = users.distinct("displayName") if users is not None else []
    except Exception:
        names = []
    if not names:
        names = static_employee_names
    dynamic["employee_names"] = _unique_lower(names)

    value_synonyms = dynamic["value_synonyms"]
    value_synonyms["location"] = _build_value_synonyms(_collect_values(locations, fallback_vals("location")))
    value_synonyms["role"] = _build_value_synonyms(_collect_values(roles, fallback_vals("role")))
    value_synonyms["employment-type"] = _build_value_synonyms(_collect_values(employment_types, fallback_vals("employment-type")))
    value_synonyms["manager"] = _build_value_synonyms(_collect_values(managers, fallback_vals("manager")))
    value_synonyms["directory-group"] = _build_value_synonyms(_collect_values(directory_groups, fallback_vals("directory-group")))
    value_synonyms["department"] = _build_value_synonyms(_collect_values(departments, fallback_vals("department")))

    # Tags: gather from users.tags array if present
    tag_values: List[str] = []
    try:
        if users is not None:
            tag_values = [v for v in users.distinct("tags") if v]
    except Exception:
        tag_values = []
    if not tag_values:
        tag_values = fallback_vals("tags")
    value_synonyms["tags"] = _build_value_synonyms(_unique_lower(tag_values))

    # Users “all users” bucket: keep static if present
    if "user" in static_value_syn:
        value_synonyms["user"] = static_value_syn["user"]

    return dynamic
