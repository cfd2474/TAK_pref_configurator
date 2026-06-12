#!/usr/bin/env python3
"""Extract TAK-CIV preference schema from the atak-civ GitHub repository."""

from __future__ import annotations

import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ATAK_REPO = "https://raw.githubusercontent.com/TAK-Product-Center/atak-civ/main"
OUTPUT = Path(__file__).resolve().parents[1] / "backend" / "data" / "preference_schema.json"
ANDROID_NS = "{http://schemas.android.com/apk/res/android}"

# Fields with known discrete values not declared as ListPreference in XML.
FIELD_OVERRIDES: dict[str, dict] = {
    "caLocation": {
        "type": "select",
        "options": [
            {"label": "Built-in CA", "value": "(built-in)"},
            {"label": "Custom file path", "value": "__custom__"},
        ],
        "allow_custom": True,
    },
    "certificateLocation": {
        "type": "select",
        "options": [
            {"label": "Built-in certificate", "value": "(built-in)"},
            {"label": "Custom file path", "value": "__custom__"},
        ],
        "allow_custom": True,
    },
}

BOOLEAN_OPTIONS = [
    {"label": "True", "value": "true"},
    {"label": "False", "value": "false"},
]


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url) as response:
        return response.read()


def resolve_ref(value: str, strings: dict[str, str], arrays: dict[str, list[str]]) -> str:
    if not value:
        return ""
    string_match = re.match(r"@string/(\w+)", value)
    if string_match:
        return strings.get(string_match.group(1), string_match.group(1))
    array_match = re.match(r"@array/(\w+)", value)
    if array_match:
        return array_match.group(1)
    return value


def load_strings() -> dict[str, str]:
    root = ET.fromstring(fetch(f"{ATAK_REPO}/atak/ATAK/app/src/main/res/values/strings.xml"))
    strings: dict[str, str] = {}
    for elem in root.findall("string"):
        name = elem.attrib.get("name")
        if name:
            strings[name] = "".join(elem.itertext()).strip()
    return strings


def load_arrays(strings: dict[str, str]) -> dict[str, list[str]]:
    root = ET.fromstring(fetch(f"{ATAK_REPO}/atak/ATAK/app/src/main/res/values/arrays.xml"))
    arrays: dict[str, list[str]] = {}
    for elem in root.findall("string-array"):
        name = elem.attrib.get("name")
        if not name:
            continue
        values = []
        for item in elem.findall("item"):
            text = (item.text or "").strip()
            if text.startswith("@string/"):
                key = text.replace("@string/", "")
                text = strings.get(key, key)
            values.append(text)
        arrays[name] = values
    return arrays


def resolve_options(
    entries_ref: str,
    values_ref: str,
    arrays: dict[str, list[str]],
) -> list[dict[str, str]]:
    entries_name = entries_ref.replace("@array/", "") if entries_ref.startswith("@array/") else entries_ref
    values_name = values_ref.replace("@array/", "") if values_ref.startswith("@array/") else values_ref
    labels = arrays.get(entries_name, [])
    values = arrays.get(values_name, labels)
    if not labels:
        return []
    options = []
    for index, label in enumerate(labels):
        value = values[index] if index < len(values) else label
        options.append({"label": label, "value": value})
    return options


def get_attr(elem: ET.Element, name: str) -> str:
    return elem.attrib.get(ANDROID_NS + name, "")


def infer_field(elem: ET.Element, strings: dict[str, str], arrays: dict[str, list[str]]) -> dict:
    tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
    key = get_attr(elem, "key")

    field: dict = {
        "key": key,
        "title": resolve_ref(get_attr(elem, "title"), strings, arrays) or key,
        "summary": resolve_ref(get_attr(elem, "summary"), strings, arrays),
        "default": get_attr(elem, "defaultValue") or None,
        "widget": tag,
    }

    entries = get_attr(elem, "entries")
    entry_values = get_attr(elem, "entryValues")

    if "MultiSelect" in tag and entries:
        options = resolve_options(entries, entry_values or entries, arrays)
        field["type"] = "multiselect"
        field["options"] = options
        return field

    if "ListPreference" in tag and entries:
        options = resolve_options(entries, entry_values or entries, arrays)
        field["type"] = "select"
        field["options"] = options
        return field

    if "CheckBox" in tag or tag == "SwitchPreference":
        field["type"] = "boolean"
        field["input"] = "select"
        field["options"] = BOOLEAN_OPTIONS
        return field

    if tag == "SeekBarPreference":
        field["type"] = "integer"
        return field

    input_type = get_attr(elem, "inputType")
    if "number" in input_type or "numeric" in input_type:
        field["type"] = "integer"
        return field

    field["type"] = "string"
    return field


def apply_overrides(field: dict) -> dict:
    override = FIELD_OVERRIDES.get(field["key"])
    if override:
        field.update(override)
    return field


def main() -> int:
    tree = json.loads(
        fetch("https://api.github.com/repos/TAK-Product-Center/atak-civ/git/trees/main?recursive=1")
    )
    xml_files = sorted(
        item["path"]
        for item in tree.get("tree", [])
        if item["path"].startswith("atak/ATAK/app/src/main/res/xml/")
        and item["path"].endswith(".xml")
        and (
            "preference" in item["path"].lower()
            or Path(item["path"]).name.startswith("basic_display")
            or Path(item["path"]).name.startswith("display_")
        )
    )

    strings = load_strings()
    arrays = load_arrays(strings)
    categories = []

    for xml_path in xml_files:
        xml_name = Path(xml_path).name
        try:
            root = ET.fromstring(fetch(f"{ATAK_REPO}/{xml_path}"))
        except ET.ParseError:
            continue

        category = {
            "id": Path(xml_name).stem,
            "file": xml_name,
            "title": Path(xml_name).stem.replace("_", " ").title(),
            "sections": [],
            "fields": [],
        }
        current_section = None

        def walk(node: ET.Element) -> None:
            nonlocal current_section
            tag = node.tag.split("}")[-1] if "}" in node.tag else node.tag

            if tag == "PreferenceCategory":
                title = resolve_ref(get_attr(node, "title"), strings, arrays) or get_attr(node, "key") or "General"
                current_section = {"title": title, "key": get_attr(node, "key"), "fields": []}
                category["sections"].append(current_section)
                for child in node:
                    walk(child)
                return

            key = get_attr(node, "key")
            if key and tag != "PreferenceScreen":
                field = apply_overrides(infer_field(node, strings, arrays))
                if current_section is not None:
                    current_section["fields"].append(field)
                else:
                    category["fields"].append(field)

            for child in node:
                if tag != "PreferenceCategory":
                    walk(child)

        walk(root)
        if category["sections"] or category["fields"]:
            categories.append(category)

    connection_fields = [
        {
            "key": "connectString",
            "title": "Connection",
            "type": "connect_string",
            "required": True,
            "help": "Built from protocol, host, port, and interface below.",
            "parts": {
                "proto": {
                    "label": "Protocol",
                    "type": "select",
                    "options": [
                        {"label": "SSL/TLS", "value": "ssl"},
                        {"label": "TCP", "value": "tcp"},
                        {"label": "UDP", "value": "udp"},
                        {"label": "QUIC", "value": "quic"},
                    ],
                    "default": "ssl",
                },
                "host": {"label": "Host", "type": "string", "placeholder": "takserver.example.com"},
                "port": {"label": "Port", "type": "integer", "default": 8089},
                "iface": {
                    "label": "Interface",
                    "type": "select",
                    "options": [
                        {"label": "Stream", "value": "stream"},
                        {"label": "Streaming", "value": "streaming"},
                    ],
                    "default": "stream",
                },
            },
        },
        {"key": "description", "title": "Description", "type": "string"},
        {
            "key": "enabled",
            "title": "Enabled",
            "type": "boolean",
            "input": "select",
            "options": BOOLEAN_OPTIONS,
            "default": True,
        },
        {
            "key": "useAuth",
            "title": "Use Authentication",
            "type": "boolean",
            "input": "select",
            "options": BOOLEAN_OPTIONS,
            "default": False,
        },
        {
            "key": "compress",
            "title": "Compress",
            "type": "boolean",
            "input": "select",
            "options": BOOLEAN_OPTIONS,
            "default": False,
        },
        {
            "key": "cacheCreds",
            "title": "Cache Credentials",
            "type": "select",
            "options": [
                {"label": "Do Not Cache", "value": "Do Not Cache"},
                {"label": "Cache Username", "value": "Cache Username"},
                {"label": "Cache Username and Password", "value": "Cache Username and Password"},
            ],
        },
        {
            "key": "caLocation",
            "title": "CA Location",
            "type": "select",
            "options": [
                {"label": "Built-in CA", "value": "(built-in)"},
                {"label": "Custom file path", "value": "__custom__"},
            ],
            "allow_custom": True,
        },
        {
            "key": "certificateLocation",
            "title": "Certificate Location",
            "type": "select",
            "options": [
                {"label": "Built-in certificate", "value": "(built-in)"},
                {"label": "Custom file path", "value": "__custom__"},
            ],
            "allow_custom": True,
        },
        {"key": "caPassword", "title": "CA Password", "type": "string", "sensitive": True, "input": "password"},
        {"key": "clientPassword", "title": "Client Password", "type": "string", "sensitive": True, "input": "password"},
        {
            "key": "enrollForCertificateWithTrust",
            "title": "Enroll For Certificate With Trust",
            "type": "boolean",
            "input": "select",
            "options": BOOLEAN_OPTIONS,
            "default": False,
        },
        {
            "key": "enrollUseTrust",
            "title": "Enroll Use Trust",
            "type": "boolean",
            "input": "select",
            "options": BOOLEAN_OPTIONS,
            "default": False,
        },
        {"key": "expiration", "title": "Expiration", "type": "integer", "default": -1},
    ]

    select_count = 0
    multiselect_count = 0
    for category in categories:
        all_fields = category["fields"] + [f for s in category["sections"] for f in s["fields"]]
        for field in all_fields:
            if field.get("type") == "select":
                select_count += 1
            if field.get("type") == "multiselect":
                multiselect_count += 1

    schema = {
        "product": "TAK-CIV",
        "version": "5.5.1",
        "source": "https://github.com/TAK-Product-Center/atak-civ",
        "main_prefs": {
            "preference_group": "com.atakmap.civ_preferences",
            "preference_groups": [
                "cot_inputs",
                "cot_outputs",
                "cot_streams",
                "com.atakmap.civ_preferences",
            ],
            "excluded_keys": ["locationCallsign", "bestDeviceUID"],
        },
        "connections": {
            "groups": [
                {"name": "cot_inputs", "title": "CoT Inputs", "description": "Incoming connection endpoints"},
                {"name": "cot_outputs", "title": "CoT Outputs", "description": "Outgoing connection endpoints"},
                {"name": "cot_streams", "title": "CoT Streams", "description": "Streaming server connections"},
            ],
            "connection_fields": connection_fields,
        },
        "categories": categories,
        "stats": {
            "category_count": len(categories),
            "field_count": sum(
                len(c["fields"]) + sum(len(s["fields"]) for s in c["sections"]) for c in categories
            ),
            "select_fields": select_count,
            "multiselect_fields": multiselect_count,
        },
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT}")
    print(json.dumps(schema["stats"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
