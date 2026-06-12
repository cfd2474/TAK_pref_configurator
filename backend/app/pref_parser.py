"""Parse ATAK .pref XML files into structured configuration data."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any

from .xml_utils import decode_value

CONNECTION_GROUPS = ("cot_inputs", "cot_outputs", "cot_streams")

JAVA_TYPE_MAP = {
    "class java.lang.String": "string",
    "class java.lang.Boolean": "boolean",
    "class java.lang.Integer": "integer",
    "class java.lang.Float": "float",
    "class java.lang.Long": "long",
}


def _parse_value(class_name: str, entry: ET.Element) -> Any:
    if "HashSet" in class_name or "Set" in class_name:
        return [
            decode_value(el.text or "")
            for el in entry.findall("element")
            if el.text is not None
        ]

    text = entry.text or ""
    value_type = JAVA_TYPE_MAP.get(class_name, "string")
    decoded = decode_value(text)

    if value_type == "boolean":
        return decoded.lower() == "true"
    if value_type == "integer":
        return int(decoded) if decoded else 0
    if value_type == "long":
        return int(decoded) if decoded else 0
    if value_type == "float":
        return float(decoded) if decoded else 0.0
    return decoded


def _parse_connections(entries: dict[str, Any]) -> list[dict[str, Any]]:
    count = int(entries.get("count", 0))
    connections: list[dict[str, Any]] = []
    suffix_pattern = re.compile(r"(\d+)$")

    for index in range(count):
        conn: dict[str, Any] = {}
        for key, value in entries.items():
            if key == "count":
                continue
            match = suffix_pattern.search(key)
            if not match or int(match.group(1)) != index:
                continue
            field_key = key[: match.start()]
            conn[field_key] = value
        if conn:
            connections.append(conn)
    return connections


def parse_pref_xml(content: str) -> dict[str, Any]:
    root = ET.fromstring(content)
    result: dict[str, Any] = {
        "preference_name": "com.atakmap.civ_preferences",
        "connections": {group: [] for group in CONNECTION_GROUPS},
        "preferences": {},
    }

    for preference in root.findall("preference"):
        name = preference.get("name", "")
        entries: dict[str, Any] = {}

        for entry in preference.findall("entry"):
            key = decode_value(entry.get("key", ""))
            class_name = entry.get("class", "class java.lang.String")
            entries[key] = _parse_value(class_name, entry)

        if name in CONNECTION_GROUPS:
            result["connections"][name] = _parse_connections(entries)
        else:
            result["preference_name"] = name
            for key, value in entries.items():
                if isinstance(value, bool):
                    value_type = "boolean"
                elif isinstance(value, int):
                    value_type = "long" if abs(value) > 2_147_483_647 else "integer"
                elif isinstance(value, float):
                    value_type = "float"
                elif isinstance(value, list):
                    value_type = "set"
                else:
                    value_type = "string"
                result["preferences"][key] = {"type": value_type, "value": value}

    return result
