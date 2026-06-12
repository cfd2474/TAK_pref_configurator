"""Generate ATAK .pref XML files from structured configuration data."""

from __future__ import annotations

from typing import Any

from .xml_utils import encode_value, escape_xml_attr, java_class_for_type

DEFAULT_APP_PREFS = "com.atakmap.civ_preferences"
CONNECTION_GROUPS = ("cot_inputs", "cot_outputs", "cot_streams")


def _stringify_value(value: Any, value_type: str) -> str:
    if value_type == "boolean":
        return "true" if bool(value) else "false"
    return str(value) if value is not None else ""


def _format_entry(key: str, value: Any, value_type: str) -> str:
    java_class = java_class_for_type(value_type)
    encoded_key = escape_xml_attr(encode_value(key))

    if value_type == "set" and isinstance(value, list):
        elements = []
        for item in value:
            text = encode_value(str(item)) if item is not None else ""
            elements.append(f"      <element>{text}</element>\r\n")
        body = "\r\n" + "".join(elements)
        return (
            f'    <entry key="{encoded_key}" class="{java_class}">{body}'
            f"    </entry>\r\n"
        )

    text = encode_value(_stringify_value(value, value_type))
    return f'    <entry key="{encoded_key}" class="{java_class}">{text}</entry>\r\n'


def _connection_entries(connections: list[dict[str, Any]]) -> list[tuple[str, Any, str]]:
    entries: list[tuple[str, Any, str]] = [("count", len(connections), "integer")]
    for index, conn in enumerate(connections):
        for field_key, value in conn.items():
            if value is None or value == "":
                continue
            if isinstance(value, bool):
                entries.append((f"{field_key}{index}", value, "boolean"))
            elif isinstance(value, int) and field_key == "expiration":
                entries.append((f"{field_key}{index}", value, "long"))
            elif isinstance(value, int):
                entries.append((f"{field_key}{index}", value, "integer"))
            elif isinstance(value, float):
                entries.append((f"{field_key}{index}", value, "float"))
            else:
                entries.append((f"{field_key}{index}", value, "string"))
    return entries


def generate_pref_xml(config: dict[str, Any]) -> str:
    """
    Build a .pref file from config:
    {
      "preference_name": "com.atakmap.civ_preferences",
      "connections": {"cot_streams": [...], ...},
      "preferences": {"key": {"type": "boolean", "value": true}, ...}
    }
    """
    lines = [
        "<?xml version='1.0' standalone='yes'?>\r\n",
        "<preferences>\r\n",
    ]

    connections = config.get("connections", {})
    for group in CONNECTION_GROUPS:
        group_connections = connections.get(group, [])
        if not group_connections:
            continue
        lines.append(f'  <preference name="{group}">\r\n')
        for key, value, value_type in _connection_entries(group_connections):
            lines.append(_format_entry(key, value, value_type))
        lines.append("  </preference>\r\n")

    preferences = config.get("preferences", {})
    if preferences:
        pref_name = config.get("preference_name", DEFAULT_APP_PREFS)
        lines.append(f'  <preference name="{pref_name}">\r\n')
        for key, pref in preferences.items():
            if not pref or pref.get("value") is None or pref.get("value") == "":
                continue
            value_type = pref.get("type", "string")
            lines.append(_format_entry(key, pref["value"], value_type))
        lines.append("  </preference>\r\n")

    lines.append("</preferences>\r\n")
    return "".join(lines)
