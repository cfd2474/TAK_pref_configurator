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


def test_reference_string_ports_use_string_storage() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    enriched = enrich_schema(schema)
    fields = _schema_fields(enriched)
    assert fields["listenPort"]["storage_type"] == "string"
    assert fields["apiSecureServerPort"]["storage_type"] == "string"


def test_missing_reference_keys_are_added() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    base_keys = set(_schema_fields(schema))
    enriched = enrich_schema(schema)
    enriched_keys = set(_schema_fields(enriched))
    assert "atakRoleType" in enriched_keys
    assert len(enriched_keys) > len(base_keys)
