"""Validate schema enrichment against ATAK Core preference reference."""

from __future__ import annotations

import json
from pathlib import Path

from backend.app.schema_enricher import enrich_schema, load_reference

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "backend" / "data" / "preference_schema.json"


def _schema_fields(schema: dict) -> dict[str, dict]:
    fields: dict[str, dict] = {}
    for category in schema["categories"]:
        for field in category.get("fields", []):
            fields[field["key"]] = field
        for section in category.get("sections", []):
            for field in section.get("fields", []):
                fields[field["key"]] = field
    return fields


def test_reference_file_loaded() -> None:
    reference = load_reference()
    assert reference["keys"]
    assert reference["stats"]["exportable_keys"] > 200


def test_enriched_schema_includes_reference_metadata() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    enriched = enrich_schema(schema)
    assert enriched["reference"]["atak_core"]["source"] == "ATAK-Preferences-Key.xlsx"


def test_reference_enumerations_become_select_fields() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    enriched = enrich_schema(schema)
    fields = _schema_fields(enriched)
    assert fields["locationTeam"]["type"] == "select"
    assert len(fields["locationTeam"]["options"]) >= 10
    assert fields["atakRoleType"]["type"] == "select"
    assert any(option["value"] == "Team Lead" for option in fields["atakRoleType"]["options"])


def test_action_keys_map_to_reference_pref_keys() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    enriched = enrich_schema(schema)
    fields = _schema_fields(enriched)
    role_field = fields["atakRoleType"]
    assert role_field["type"] == "select"
    assert len(role_field["options"]) == 8
    assert "atakRoleTypeAction" not in fields
    display_field = fields["locationUnitType"]
    assert display_field["type"] == "select"
    assert len(display_field["options"]) >= 6


def test_reference_string_ports_use_string_storage() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    enriched = enrich_schema(schema)
    fields = _schema_fields(enriched)
    assert fields["listenPort"]["storage_type"] == "string"
    assert fields["apiSecureServerPort"]["storage_type"] == "string"


def test_color_fields_use_color_picker() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    enriched = enrich_schema(schema)
    fields = _schema_fields(enriched)
    track_color = fields["track_history_default_color"]
    assert track_color["input"] == "color"
    assert track_color["color_format"] == "android_int"
    toolbar_color = fields["actionbar_icon_color_key"]
    assert toolbar_color["input"] == "color"
    assert toolbar_color["color_format"] == "hex"


def test_nav_orientation_right_uses_left_right_labels() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    enriched = enrich_schema(schema)
    fields = _schema_fields(enriched)
    toolbar_side = fields["nav_orientation_right"]
    assert [option["label"] for option in toolbar_side["options"]] == ["Left", "Right"]
    assert [option["value"] for option in toolbar_side["options"]] == ["false", "true"]


def test_pref_grid_color_uses_palette_picker() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    enriched = enrich_schema(schema)
    fields = _schema_fields(enriched)
    grid_color = fields["pref_grid_color"]
    assert grid_color["input"] == "palette_color"
    assert len([option for option in grid_color["options"] if option["value"].startswith("#")]) >= 4


def test_adjust_toolbar_section_expands_to_actionable_fields() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    enriched = enrich_schema(schema)
    display = next(category for category in enriched["categories"] if category["id"] == "display_preferences")
    section_titles = [section["title"] for section in display.get("sections", [])]
    assert "My Location Color / Size" in section_titles
    assert "Tool Bar Customization" in section_titles
    assert "Adjust Toolbar Preferences" not in section_titles

    fields = _schema_fields(enriched)
    assert fields["location_marker_scale_key"]["type"] == "select"
    assert fields["gps_icon_color_mode"]["input"] == "gps_icon_color_mode"
    assert fields["nav_orientation_right"]["options"][0]["label"] == "Left"
    display_keys = {
        field["key"]
        for section in display.get("sections", [])
        for field in section.get("fields", [])
    }
    assert "my_location_icon_color" not in display_keys
    assert "my_actionbar_settings" not in display_keys

    by_id = {category["id"]: category for category in enriched["categories"]}
    assert by_id["ref_color_category"].get("nav_hidden") is True
    assert by_id["custom_actionbar_preferences"].get("nav_hidden") is True


def test_device_preferences_nav_label_and_duplicate_hidden() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    enriched = enrich_schema(schema)
    by_id = {category["id"]: category for category in enriched["categories"]}
    assert by_id["device_preferences"]["title"] == "Device/Callsign Preferences"
    assert by_id["call_sign_preference"].get("nav_hidden") is True
    assert by_id["importstyle_preferences"]["title"] == "Import Style Preferences"
    assert by_id["geocoder_preference_fragment"]["title"] == "GeoCoder Preference"
    assert by_id["missionpackage_preferences"]["title"] == "Mission Package Preferences"
    assert by_id["lrf_preferences"]["title"] == "LRF Preferences"
    assert by_id["off_scr_indi_preferences"]["title"] == "Off Screen Indicator Preferences"
    assert by_id["takgov_eud_preferences"]["title"] == "TAK.GOV EUD Preferences"
    assert by_id["wms_preferences"]["title"] == "WMS Preferences"


def test_route_and_radius_fields_clarify_meter_units() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    enriched = enrich_schema(schema)
    fields = _schema_fields(enriched)

    walking_bubble = fields["waypointBubble.Walking"]
    assert walking_bubble["title"].endswith("(m)")
    assert "meters" in walking_bubble["summary"].lower()
    assert walking_bubble["placeholder"] == "Enter distance in meters (m)"

    off_route = fields["waypointOffRouteBubble.Driving"]
    assert off_route["title"].endswith("(m)")
    assert "off route" in off_route["summary"].lower()
    assert "meters" in off_route["summary"].lower()

    billboard = fields["route_billboard_distance_m"]
    assert billboard["title"].endswith("(m)")
    assert "meters" in billboard["summary"].lower()

    bullseye = fields["bullseyeRadiusRings"]
    assert bullseye["title"] == "Bullseye Ring Radius (m)"

    reroute = fields["bloodhound_reroute_distance_pref"]
    assert reroute["title"] == "Reroute Distance (m)"
    assert "meters" in reroute["summary"].lower()

    smart_cache_limit = fields["prefs_smart_cache_download_limit"]
    assert smart_cache_limit["title"].endswith("(bytes)")
    assert "bytes" in smart_cache_limit["summary"].lower()
    assert smart_cache_limit["placeholder"] == "Limit in bytes (e.g. 5000000)"


def test_missing_reference_keys_are_added() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    base_keys = set(_schema_fields(schema))
    enriched = enrich_schema(schema)
    enriched_keys = set(_schema_fields(enriched))
    assert "atakRoleType" in enriched_keys
    assert len(enriched_keys) > len(base_keys)
