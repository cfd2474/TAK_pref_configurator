"""Parse TAK-CIV .pref XML files into structured configuration data."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any

from .xml_utils import decode_value

CONNECTION_GROUPS = ("cot_inputs", "cot_outputs", "cot_streams")
DEFAULT_APP_PREFS = "com.atakmap.app.civ_preferences"
LEGACY_APP_PREFS = {
    "com.atakmap.app_preferences",
    "com.atakmap.civ_preferences",
    "com.atakmap.fvey_preferences",
    DEFAULT_APP_PREFS,
}

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


def _type_from_java_class(class_name: str) -> str:
    if "HashSet" in class_name or "Set" in class_name:
        return "set"
    return JAVA_TYPE_MAP.get(class_name, "string")


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


def _is_app_preference_group(name: str) -> bool:
    return name in LEGACY_APP_PREFS or name.endswith(".civ_preferences")


def parse_pref_xml(content: str) -> dict[str, Any]:
    root = ET.fromstring(content)
    result: dict[str, Any] = {
        "preference_name": DEFAULT_APP_PREFS,
        "connections": {group: [] for group in CONNECTION_GROUPS},
        "preferences": {},
    }

    for preference in root.findall("preference"):
        name = preference.get("name", "")
        parsed_entries: list[tuple[str, str, Any]] = []

        for entry in preference.findall("entry"):
            key = decode_value(entry.get("key", ""))
            class_name = entry.get("class", "class java.lang.String")
            parsed_entries.append((key, class_name, _parse_value(class_name, entry)))

        if name in CONNECTION_GROUPS:
            flat = {key: value for key, _class_name, value in parsed_entries}
            result["connections"][name] = _parse_connections(flat)
            continue

        if not _is_app_preference_group(name):
            continue

        result["preference_name"] = DEFAULT_APP_PREFS
        for key, class_name, value in parsed_entries:
            result["preferences"][key] = {
                "type": _type_from_java_class(class_name),
                "value": value,
                "java_class": class_name,
            }

    return result
