"""Generate TAK-CIV .pref XML files from structured configuration data."""

from __future__ import annotations

from typing import Any

from .xml_utils import encode_value, escape_xml_attr, java_class_for_type

DEFAULT_APP_PREFS = "com.atakmap.app.civ_preferences"
CONNECTION_GROUPS = ("cot_inputs", "cot_outputs", "cot_streams")
PREFERENCE_VERSION = "1"


def _stringify_value(value: Any, value_type: str) -> str:
    if value_type == "boolean":
        return "true" if bool(value) else "false"
    return str(value) if value is not None else ""


def _resolve_java_class(value_type: str, java_class: str | None = None) -> str:
    if java_class:
        return java_class
    return java_class_for_type(value_type)


def _format_entry(
    key: str,
    value: Any,
    value_type: str,
    java_class: str | None = None,
) -> str:
    resolved_class = _resolve_java_class(value_type, java_class)
    encoded_key = escape_xml_attr(encode_value(key))

    if value_type == "set" and isinstance(value, list):
        elements = []
        for item in value:
            text = encode_value(str(item)) if item is not None else ""
            elements.append(f"<element>{text}</element>\r\n")
        body = "\r\n" + "".join(elements)
        return (
            f'<entry key="{encoded_key}" class="{resolved_class}">{body}'
            f"</entry>\r\n"
        )

    text = encode_value(_stringify_value(value, value_type))
    return f'<entry key="{encoded_key}" class="{resolved_class}">{text}</entry>\r\n'


def _connection_entries(connections: list[dict[str, Any]]) -> list[tuple[str, Any, str, str | None]]:
    entries: list[tuple[str, Any, str, str | None]] = [
        ("count", len(connections), "integer", None)
    ]
    for index, conn in enumerate(connections):
        for field_key, value in conn.items():
            if value is None or value == "":
                continue
            java_class = None
            if isinstance(value, bool):
                value_type = "boolean"
            elif isinstance(value, int) and field_key == "expiration":
                value_type = "long"
            elif isinstance(value, int):
                value_type = "integer"
            elif isinstance(value, float):
                value_type = "float"
            else:
                value_type = "string"
            entries.append((f"{field_key}{index}", value, value_type, java_class))
    return entries


def _format_preference_block(name: str, body: str) -> str:
    return (
        f'<preference version="{PREFERENCE_VERSION}" name="{name}">\r\n'
        f"{body}"
        f"</preference>\r\n"
    )


def generate_pref_xml(config: dict[str, Any]) -> str:
    """
    Build a .pref file from config:
    {
      "preference_name": "com.atakmap.app.civ_preferences",
      "connections": {"cot_streams": [...], ...},
      "preferences": {"key": {"type": "boolean", "value": true}, ...},
      "include_empty_connection_groups": true
    }
    """
    lines = [
        "<?xml version='1.0' standalone='yes'?>\r\n",
        "<preferences>\r\n",
    ]

    connections = config.get("connections", {})
    include_empty_groups = config.get("include_empty_connection_groups", True)

    for group in CONNECTION_GROUPS:
        group_connections = connections.get(group, [])
        if not group_connections and not include_empty_groups:
            continue
        body = ""
        if group_connections:
            for key, value, value_type, java_class in _connection_entries(group_connections):
                body += _format_entry(key, value, value_type, java_class)
        lines.append(_format_preference_block(group, body))

    preferences = config.get("preferences", {})
    if preferences:
        pref_name = config.get("preference_name", DEFAULT_APP_PREFS)
        body = ""
        for key, pref in preferences.items():
            if not pref or pref.get("value") is None or pref.get("value") == "":
                continue
            if pref.get("type") == "set" and isinstance(pref.get("value"), list) and not pref["value"]:
                continue
            value_type = pref.get("type", "string")
            body += _format_entry(
                key,
                pref["value"],
                value_type,
                pref.get("java_class"),
            )
        lines.append(_format_preference_block(pref_name, body))

    lines.append("</preferences>\r\n")
    return "".join(lines)
