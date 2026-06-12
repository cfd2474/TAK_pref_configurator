"""Validate pref configuration before export."""

from __future__ import annotations

from typing import Any

CONNECTION_GROUPS = ("cot_inputs", "cot_outputs", "cot_streams")

GROUP_LABELS = {
    "cot_inputs": "CoT Input",
    "cot_outputs": "CoT Output",
    "cot_streams": "CoT Stream",
}

PREF_TYPES = frozenset({"boolean", "integer", "string", "float", "set"})


def validate_connections(connections: dict[str, list[dict[str, Any]]]) -> list[str]:
    """Watchtower requires Description and Connect String for each CoT setting."""
    errors: list[str] = []
    for group in CONNECTION_GROUPS:
        for index, conn in enumerate(connections.get(group, [])):
            label = GROUP_LABELS[group]
            name = conn.get("description") or conn.get("connectString") or f"#{index + 1}"
            if not str(conn.get("description", "")).strip():
                errors.append(f"{label} ({name}): Description is required")
            if not str(conn.get("connectString", "")).strip():
                errors.append(f"{label} ({name}): Connect string is required")
    return errors
