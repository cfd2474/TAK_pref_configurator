"""Extract ATAK/Android preference fields from preference XML."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

ANDROID_NS = "{http://schemas.android.com/apk/res/android}"

BOOLEAN_OPTIONS = [
    {"label": "True", "value": "true"},
    {"label": "False", "value": "false"},
]

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


def parse_strings_xml(xml_bytes: bytes) -> dict[str, str]:
    strings: dict[str, str] = {}
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return strings
    for elem in root.findall("string"):
        name = elem.attrib.get("name")
        if name:
            strings[name] = "".join(elem.itertext()).strip()
    return strings


def parse_arrays_xml(xml_bytes: bytes, strings: dict[str, str]) -> dict[str, list[str]]:
    arrays: dict[str, list[str]] = {}
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return arrays
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
    return elem.attrib.get(ANDROID_NS + name, elem.attrib.get(name, ""))


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
        field["storage_type"] = "set"
        field["java_class"] = "class java.util.HashSet"
        return field

    if "ListPreference" in tag and entries:
        options = resolve_options(entries, entry_values or entries, arrays)
        field["type"] = "select"
        field["options"] = options
        field["storage_type"] = "string"
        field["java_class"] = "class java.lang.String"
        return field

    if "CheckBox" in tag or tag == "SwitchPreference":
        field["type"] = "boolean"
        field["input"] = "select"
        field["options"] = BOOLEAN_OPTIONS
        field["storage_type"] = "boolean"
        field["java_class"] = "class java.lang.Boolean"
        return field

    if tag == "SeekBarPreference":
        field["type"] = "integer"
        return field

    input_type = get_attr(elem, "inputType")
    if "number" in input_type or "numeric" in input_type:
        field["type"] = "integer"
        field["storage_type"] = "string"
        field["java_class"] = "class java.lang.String"
        return field

    field["type"] = "string"
    return field


def apply_overrides(field: dict) -> dict:
    override = FIELD_OVERRIDES.get(field["key"])
    if override:
        field.update(override)
    return field


def extract_category_from_xml(
    xml_bytes: bytes,
    *,
    source_name: str,
    category_id: str | None = None,
    title: str | None = None,
    strings: dict[str, str] | None = None,
    arrays: dict[str, list[str]] | None = None,
) -> dict | None:
    """Parse one preference XML document into a category dict."""
    strings = strings or {}
    arrays = arrays or {}

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None

    xml_name = Path(source_name).name
    category = {
        "id": category_id or Path(xml_name).stem,
        "file": xml_name,
        "title": title or Path(xml_name).stem.replace("_", " ").title(),
        "sections": [],
        "fields": [],
    }
    current_section = None

    def walk(node: ET.Element) -> None:
        nonlocal current_section
        tag = node.tag.split("}")[-1] if "}" in node.tag else node.tag

        if tag == "PreferenceCategory":
            section_title = (
                resolve_ref(get_attr(node, "title"), strings, arrays)
                or get_attr(node, "key")
                or "General"
            )
            current_section = {"title": section_title, "key": get_attr(node, "key"), "fields": []}
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
    if not category["sections"] and not category["fields"]:
        return None
    return category


def count_fields(category: dict) -> int:
    return len(category.get("fields", [])) + sum(
        len(section.get("fields", [])) for section in category.get("sections", [])
    )
