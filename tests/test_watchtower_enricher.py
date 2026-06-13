"""Validate Watchtower MDM enrichment against scraped ATAK settings."""

from __future__ import annotations

import json
from pathlib import Path

from backend.app.schema_enricher import enrich_schema
from backend.app.watchtower_enricher import load_watchtower

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


def test_watchtower_reference_loaded() -> None:
    watchtower = load_watchtower()
    assert watchtower["keys"]
    assert watchtower["stats"]["total"] >= 180


def test_tristate_boolean_fields() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    enriched = enrich_schema(schema)
    fields = _schema_fields(enriched)

    log_tracks = fields["toggle_log_tracks"]
    assert log_tracks["input"] == "tristate"
    assert log_tracks["type"] == "boolean"
    assert len(log_tracks["options"]) == 3
    assert log_tracks["options"][0]["label"] == "Not set"


def test_select_fields_keep_unset_behavior() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    enriched = enrich_schema(schema)
    fields = _schema_fields(enriched)

    team = fields["locationTeam"]
    assert team["type"] == "select"
    assert all(option["value"] != "Unset" for option in team["options"])


def test_xlsx_overrides_watchtower_text_for_display_type() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    enriched = enrich_schema(schema)
    fields = _schema_fields(enriched)

    display_type = fields["locationUnitType"]
    assert display_type["type"] == "select"
    assert len(display_type["options"]) >= 6


def test_boolean_from_xlsx_becomes_tristate_when_watchtower_text() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    enriched = enrich_schema(schema)
    fields = _schema_fields(enriched)

    wr_callsign = fields["locationUseWRCallsign"]
    assert wr_callsign["input"] == "tristate"
    assert wr_callsign["type"] == "boolean"


def test_action_keys_are_not_exportable() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    enriched = enrich_schema(schema)
    fields = _schema_fields(enriched)

    for key in ("savePrefs", "loadPrefs"):
        assert fields[key]["exportable"] is False


def test_enriched_schema_includes_watchtower_metadata() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    enriched = enrich_schema(schema)
    assert enriched["reference"]["watchtower"]["source"] == "Watchtower MDM System ATAK Settings"


def test_truncated_watchtower_descriptions_keep_schema_summary() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    enriched = enrich_schema(schema)
    fields = _schema_fields(enriched)

    bread_dist = fields["bread_dist_threshold"]["summary"]
    assert "Read More" not in bread_dist
    assert "2 meters" in bread_dist

    timegap = fields["bread_track_timegap_threshold"]["summary"]
    assert "Read More" not in timegap
    assert "split into separate tracks" in timegap
