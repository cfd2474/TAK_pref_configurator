"""Validate generated TAK-CIV pref output against real EUD pref patterns."""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.pref_generator import DEFAULT_APP_PREFS, generate_pref_xml
from backend.app.pref_parser import parse_pref_xml

EUD_PREF = Path("/Users/michaelleckliter/Downloads/CFD-BASIC-PREF-4-25.pref")
SCHEMA = ROOT / "backend" / "data" / "preference_schema.json"


def _schema_fields() -> dict[str, dict]:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    fields: dict[str, dict] = {}
    for category in schema["categories"]:
        for field in category.get("fields", []):
            fields[field["key"]] = field
        for section in category.get("sections", []):
            for field in section.get("fields", []):
                fields[field["key"]] = field
    return fields


def test_eud_pref_structure() -> None:
    content = EUD_PREF.read_text(encoding="utf-8")
    root = ET.fromstring(content)
    groups = root.findall("preference")

    assert groups[0].get("name") == "cot_inputs"
    assert groups[0].get("version") == "1"
    assert groups[3].get("name") == "com.atakmap.app.civ_preferences"


def test_parse_eud_pref_name_and_types() -> None:
    parsed = parse_pref_xml(EUD_PREF.read_text(encoding="utf-8"))
    assert parsed["preference_name"] == DEFAULT_APP_PREFS
    assert parsed["preferences"]["apiSecureServerPort"]["java_class"] == "class java.lang.String"
    assert parsed["preferences"]["apiSecureServerPort"]["value"] == "8443"
    assert parsed["preferences"]["coordinate_entry_tabs"]["type"] == "set"
    assert "mgrs_pane_id" in parsed["preferences"]["coordinate_entry_tabs"]["value"]


def test_schema_overlap_storage_classes_match_eud() -> None:
    parsed = parse_pref_xml(EUD_PREF.read_text(encoding="utf-8"))
    schema_fields = _schema_fields()
    mismatches: list[str] = []

    for key, pref in parsed["preferences"].items():
        field = schema_fields.get(key)
        if not field:
            continue
        expected_class = field.get("java_class")
        if not expected_class:
            continue
        actual_class = pref.get("java_class")
        if actual_class != expected_class:
            mismatches.append(f"{key}: expected {expected_class}, got {actual_class}")

    assert not mismatches, "Storage class mismatches:\n" + "\n".join(mismatches)


def test_generated_ports_use_string_storage_from_ui() -> None:
    xml = generate_pref_xml(
        {
            "preference_name": DEFAULT_APP_PREFS,
            "include_empty_connection_groups": True,
            "preferences": {
                "apiSecureServerPort": {
                    "type": "string",
                    "value": "8443",
                    "java_class": "class java.lang.String",
                }
            },
        }
    )
    assert 'name="com.atakmap.app.civ_preferences"' in xml
    assert 'version="1"' in xml
    assert '<preference version="1" name="cot_inputs">' in xml
    assert (
        '<entry key="apiSecureServerPort" class="class java.lang.String">8443</entry>' in xml
    )


def test_round_trip_subset_from_eud() -> None:
    parsed = parse_pref_xml(EUD_PREF.read_text(encoding="utf-8"))
    keys = [
        "apiSecureServerPort",
        "hostileUpdateDelay",
        "coord_display_pref",
        "coordinate_entry_tabs",
        "monitorServerConnections",
    ]
    subset = {key: parsed["preferences"][key] for key in keys}
    xml = generate_pref_xml(
        {
            "preference_name": parsed["preference_name"],
            "include_empty_connection_groups": True,
            "preferences": subset,
        }
    )
    roundtrip = parse_pref_xml(xml)
    for key in keys:
        assert roundtrip["preferences"][key]["java_class"] == parsed["preferences"][key]["java_class"]
        assert roundtrip["preferences"][key]["value"] == parsed["preferences"][key]["value"]


if __name__ == "__main__":
    test_eud_pref_structure()
    test_parse_eud_pref_name_and_types()
    test_schema_overlap_storage_classes_match_eud()
    test_generated_ports_use_string_storage_from_ui()
    test_round_trip_subset_from_eud()
    print("EUD pref compliance checks passed.")
