#!/usr/bin/env python3
"""Extract ATAK preference schema from the atak-civ GitHub repository."""

from __future__ import annotations

import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ATAK_REPO = "https://raw.githubusercontent.com/TAK-Product-Center/atak-civ/main"
OUTPUT = Path(__file__).resolve().parents[1] / "backend" / "data" / "preference_schema.json"


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url) as response:
        return response.read()


def resolve_title(value: str, strings: dict[str, str]) -> str:
    if not value:
        return ""
    match = re.match(r"@string/(\w+)", value)
    if match:
        return strings.get(match.group(1), match.group(1))
    return value


def infer_type(elem: ET.Element) -> str:
    tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
    if "CheckBox" in tag or tag == "SwitchPreference":
        return "boolean"
    if tag == "SeekBarPreference":
        return "integer"
    android_ns = "{http://schemas.android.com/apk/res/android}"
    input_type = elem.attrib.get(f"{android_ns}inputType", "")
    if "number" in input_type or "numeric" in input_type:
        return "integer"
    return "string"


def get_attr(elem: ET.Element, name: str) -> str:
    return elem.attrib.get("{http://schemas.android.com/apk/res/android}" + name, "")


def main() -> int:
    tree_url = "https://api.github.com/repos/TAK-Product-Center/atak-civ/git/trees/main?recursive=1"
    tree = json.loads(fetch(tree_url))
    xml_files = sorted(
        item["path"]
        for item in tree.get("tree", [])
        if item["path"].startswith("atak/ATAK/app/src/main/res/xml/")
        and (
            item["path"].endswith("_preferences.xml")
            or item["path"].endswith("_preference.xml")
            or item["path"].endswith("_prefs.xml")
        )
    )

    strings = {}
    strings_root = ET.fromstring(fetch(f"{ATAK_REPO}/atak/ATAK/app/src/main/res/values/strings.xml"))
    for string_elem in strings_root.findall("string"):
        name = string_elem.attrib.get("name")
        if name:
            strings[name] = "".join(string_elem.itertext()).strip()

    categories = []
    for xml_path in xml_files:
        xml_name = Path(xml_path).name
        content = fetch(f"{ATAK_REPO}/{xml_path}")
        try:
            root = ET.fromstring(content)
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
                title = resolve_title(get_attr(node, "title"), strings) or get_attr(node, "key") or "General"
                current_section = {"title": title, "key": get_attr(node, "key"), "fields": []}
                category["sections"].append(current_section)
                for child in node:
                    walk(child)
                return

            key = get_attr(node, "key")
            if key and tag != "PreferenceScreen":
                field = {
                    "key": key,
                    "title": resolve_title(get_attr(node, "title"), strings) or key,
                    "summary": resolve_title(get_attr(node, "summary"), strings),
                    "type": infer_type(node),
                    "default": get_attr(node, "defaultValue") or None,
                    "widget": tag,
                }
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

    schema = {
        "version": "5.5.1",
        "source": "https://github.com/TAK-Product-Center/atak-civ",
        "main_prefs": {
            "preference_groups": [
                "cot_inputs",
                "cot_outputs",
                "cot_streams",
                "com.atakmap.civ_preferences",
            ],
            "legacy_names": [
                "com.atakmap.app_preferences",
                "com.atakmap.civ_preferences",
                "com.atakmap.fvey_preferences",
            ],
            "excluded_keys": ["locationCallsign", "bestDeviceUID"],
        },
        "connections": {
            "groups": [
                {"name": "cot_inputs", "title": "CoT Inputs", "description": "Incoming connection endpoints"},
                {"name": "cot_outputs", "title": "CoT Outputs", "description": "Outgoing connection endpoints"},
                {"name": "cot_streams", "title": "CoT Streams", "description": "Streaming server connections"},
            ],
            "connection_fields": [
                {"key": "connectString", "title": "Connect String", "type": "string", "required": True, "help": "e.g. ssl:server.example.com:8089:stream"},
                {"key": "description", "title": "Description", "type": "string"},
                {"key": "enabled", "title": "Enabled", "type": "boolean", "default": True},
                {"key": "useAuth", "title": "Use Authentication", "type": "boolean", "default": False},
                {"key": "compress", "title": "Compress", "type": "boolean", "default": False},
                {"key": "cacheCreds", "title": "Cache Credentials", "type": "string", "options": ["Do Not Cache", "Cache Username", "Cache Username and Password"]},
                {"key": "caLocation", "title": "CA Location", "type": "string"},
                {"key": "certificateLocation", "title": "Certificate Location", "type": "string"},
                {"key": "caPassword", "title": "CA Password", "type": "string", "sensitive": True},
                {"key": "clientPassword", "title": "Client Password", "type": "string", "sensitive": True},
                {"key": "enrollForCertificateWithTrust", "title": "Enroll For Certificate With Trust", "type": "boolean", "default": False},
                {"key": "enrollUseTrust", "title": "Enroll Use Trust", "type": "boolean", "default": False},
                {"key": "expiration", "title": "Expiration", "type": "long", "default": -1},
            ],
        },
        "categories": categories,
        "stats": {
            "category_count": len(categories),
            "field_count": sum(len(c["fields"]) + sum(len(s["fields"]) for s in c["sections"]) for c in categories),
        },
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT}")
    print(json.dumps(schema["stats"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
