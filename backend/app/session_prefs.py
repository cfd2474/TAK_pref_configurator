"""Device session preferences that should not be deployed in .pref files."""

from __future__ import annotations

from typing import Any

# Point Dropper / iconset UI state — can conflict with locationUnitType on import.
SESSION_PREF_KEYS = frozenset(
    {
        "lastCoTTypeSet",
        "lastIconsetPath",
        "iconset.selected.uid",
        "iconset.selected.color",
        "iconset.display.hint2",
    }
)


def pref_value(preferences: dict[str, Any], key: str) -> Any:
    pref = preferences.get(key)
    if pref is None:
        return None
    if isinstance(pref, dict):
        return pref.get("value")
    return pref


def analyze_session_pref_issues(preferences: dict[str, Any]) -> dict[str, Any]:
    session_keys = sorted(key for key in preferences if key in SESSION_PREF_KEYS)
    warnings: list[str] = []

    unit_type = pref_value(preferences, "locationUnitType")
    last_cot = pref_value(preferences, "lastCoTTypeSet")

    if unit_type and last_cot and str(unit_type) != str(last_cot):
        warnings.append(
            "locationUnitType "
            f"({unit_type}) conflicts with lastCoTTypeSet ({last_cot}). "
            'ATAK may show Node Type as "Not Recognized [Ground Troop]" and change radial menu behavior.'
        )

    if session_keys:
        preview = ", ".join(session_keys[:5])
        if len(session_keys) > 5:
            preview += ", …"
        warnings.append(
            f"Found {len(session_keys)} device session key(s) unsuitable for deployment: {preview}."
        )

    return {
        "session_keys": session_keys,
        "warnings": warnings,
        "unit_type_conflict": bool(
            unit_type and last_cot and str(unit_type) != str(last_cot)
        ),
    }


def strip_session_preferences(preferences: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    stripped: list[str] = []
    cleaned = dict(preferences)
    for key in SESSION_PREF_KEYS:
        if key in cleaned:
            stripped.append(key)
            del cleaned[key]
    return cleaned, stripped
