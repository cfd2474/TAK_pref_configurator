"""Validate generated TAK-CIV pref output against real EUD reference files."""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.pref_generator import DEFAULT_APP_PREFS, generate_pref_xml
from backend.app.pref_parser import parse_pref_xml
from backend.app.xml_utils import sanitize_pref_xml

FIXTURES = ROOT / "tests" / "fixtures"
SCHEMA = ROOT / "backend" / "data" / "preference_schema.json"

REFERENCE_PREFS = [
    {
        "name": "cfd-basic-pref-4-25",
        "path": FIXTURES / "cfd-basic-pref-4-25.pref",
    },
    {
        "name": "leckliter-test-pref",
        "path": FIXTURES / "leckliter-test-pref.pref",
    },
]

ROUND_TRIP_KEYS = [
    "apiSecureServerPort",
    "hostileUpdateDelay",
    "coord_display_pref",
    "coordinate_entry_tabs",
    "monitorServerConnections",
    "img_cap_res",
    "bread_dist_threshold",
]


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


def _load_reference(path: Path) -> str:
    assert path.exists(), f"Missing reference pref fixture: {path}"
    return path.read_text(encoding="utf-8", errors="replace")


def test_reference_pref_structure() -> None:
    for reference in REFERENCE_PREFS:
        content = _load_reference(reference["path"])
        root = ET.fromstring(sanitize_pref_xml(content))
        groups = root.findall("preference")

        assert groups[0].get("name") == "cot_inputs", reference["name"]
        assert groups[0].get("version") == "1", reference["name"]
        assert groups[3].get("name") == DEFAULT_APP_PREFS, reference["name"]


def test_parse_reference_prefs() -> None:
    for reference in REFERENCE_PREFS:
        parsed = parse_pref_xml(_load_reference(reference["path"]))
        assert parsed["preference_name"] == DEFAULT_APP_PREFS, reference["name"]
        assert parsed["preferences"], reference["name"]

        if "apiSecureServerPort" in parsed["preferences"]:
            port = parsed["preferences"]["apiSecureServerPort"]
            assert port["java_class"] == "class java.lang.String", reference["name"]
            assert port["value"] == "8443", reference["name"]

        if "coordinate_entry_tabs" in parsed["preferences"]:
            tabs = parsed["preferences"]["coordinate_entry_tabs"]
            assert tabs["type"] == "set", reference["name"]
            assert "mgrs_pane_id" in tabs["value"], reference["name"]

        if "img_cap_res" in parsed["preferences"]:
            res = parsed["preferences"]["img_cap_res"]
            assert res["java_class"] == "class java.lang.Integer", reference["name"]
            assert res["value"] == 5, reference["name"]


def test_schema_overlap_storage_classes_match_references() -> None:
    schema_fields = _schema_fields()

    for reference in REFERENCE_PREFS:
        parsed = parse_pref_xml(_load_reference(reference["path"]))
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

        assert not mismatches, f"{reference['name']} storage class mismatches:\n" + "\n".join(mismatches)


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
    assert f'name="{DEFAULT_APP_PREFS}"' in xml
    assert 'version="1"' in xml
    assert '<preference version="1" name="cot_inputs">' in xml
    assert (
        '<entry key="apiSecureServerPort" class="class java.lang.String">8443</entry>' in xml
    )


def test_round_trip_subset_from_references() -> None:
    for reference in REFERENCE_PREFS:
        parsed = parse_pref_xml(_load_reference(reference["path"]))
        keys = [key for key in ROUND_TRIP_KEYS if key in parsed["preferences"]]
        assert keys, f"No round-trip keys found in {reference['name']}"

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
    test_reference_pref_structure()
    test_parse_reference_prefs()
    test_schema_overlap_storage_classes_match_references()
    test_generated_ports_use_string_storage_from_ui()
    test_round_trip_subset_from_references()
    print(f"EUD pref compliance checks passed for {len(REFERENCE_PREFS)} reference files.")
