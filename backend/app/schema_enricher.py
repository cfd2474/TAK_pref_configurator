"""Apply ATAK Core preference reference metadata to the UI schema."""

from __future__ import annotations

import copy
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .watchtower_enricher import apply_watchtower_enrichment

REFERENCE_PATH = Path(__file__).resolve().parent.parent / "data" / "atak_pref_reference.json"

# ATAK preference XML often uses *Action keys for navigation while .pref export keys differ.
EXPLICIT_REFERENCE_ALIASES = {
    "atakRoleTypeAction": "atakRoleType",
    "locationUnitTypeAction": "locationUnitType",
}


def load_reference(path: Path | None = None) -> dict[str, Any]:
    reference_path = path or REFERENCE_PATH
    if not reference_path.exists():
        return {"keys": {}, "categories": {}, "stats": {}}
    with reference_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def iter_schema_fields(schema: dict[str, Any]):
    for category in schema.get("categories", []):
        for field in category.get("fields", []):
            yield category, None, field
        for section in category.get("sections", []):
            for field in section.get("fields", []):
                yield category, section, field


def collect_schema_keys(schema: dict[str, Any]) -> set[str]:
    return {field["key"] for _, _, field in iter_schema_fields(schema)}


def reference_field_to_schema_field(ref: dict[str, Any]) -> dict[str, Any]:
    field: dict[str, Any] = {
        "key": ref["key"],
        "title": ref.get("item") or ref["key"],
        "summary": ref.get("reference_hint") or "",
        "type": ref.get("type", "string"),
        "source": "atak_pref_reference",
        "reference_type": ref.get("reference_type"),
        "exportable": ref.get("exportable", True),
    }
    if ref.get("options"):
        field["options"] = ref["options"]
        field["input"] = ref.get("input", "select")
    if ref.get("storage_type"):
        field["storage_type"] = ref["storage_type"]
    if ref.get("java_class"):
        field["java_class"] = ref["java_class"]
    if ref.get("reference_hint"):
        field["reference_hint"] = ref["reference_hint"]
    return field


def resolve_reference_key(field_key: str, ref_keys: dict[str, Any]) -> tuple[str, dict[str, Any]] | tuple[None, None]:
    if field_key in ref_keys:
        return field_key, ref_keys[field_key]

    alias = EXPLICIT_REFERENCE_ALIASES.get(field_key)
    if alias and alias in ref_keys:
        return alias, ref_keys[alias]

    if field_key.endswith("Action"):
        candidate = field_key[: -len("Action")]
        if candidate in ref_keys:
            return candidate, ref_keys[candidate]

    return None, None


def apply_reference_to_field(
    field: dict[str, Any],
    ref: dict[str, Any],
    *,
    canonical_key: str | None = None,
) -> None:
    if canonical_key and canonical_key != field.get("key"):
        field["schema_key"] = field["key"]
        field["key"] = canonical_key

    field["reference_type"] = ref.get("reference_type")
    field["exportable"] = ref.get("exportable", True)
    if ref.get("item"):
        field["title"] = ref["item"]
    if ref.get("reference_hint"):
        field["reference_hint"] = ref["reference_hint"]
        if not field.get("summary"):
            field["summary"] = ref["reference_hint"]

    if ref.get("options") and len(ref["options"]) >= 2:
        if ref.get("storage_type") == "boolean":
            field["type"] = "boolean"
        else:
            field["type"] = "select"
        field["options"] = ref["options"]
        field["input"] = ref.get("input", "select")
    else:
        ref_type = ref.get("type")
        if ref_type in {"boolean", "integer", "string", "select"}:
            field["type"] = ref_type

    if ref.get("storage_type"):
        field["storage_type"] = ref["storage_type"]
    if ref.get("java_class"):
        field["java_class"] = ref["java_class"]


def mark_non_exportable_navigation_fields(field: dict[str, Any]) -> None:
    if field.get("options") or field.get("exportable") is False:
        return
    widget = field.get("widget", "")
    if field["key"].endswith("Action") or widget.endswith("PanPreference"):
        field["exportable"] = False


def add_missing_reference_categories(schema: dict[str, Any], reference: dict[str, Any]) -> None:
    schema_keys = collect_schema_keys(schema)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for key, ref in reference.get("keys", {}).items():
        if key in schema_keys or not ref.get("exportable"):
            continue
        if ref.get("type") in {"selection_action", "information", "menu_item", "category"}:
            continue
        category_key = ref.get("category_key") or "reference_misc"
        grouped[category_key].append(ref)

    for category_key, refs in sorted(grouped.items()):
        category_meta = reference.get("categories", {}).get(category_key, {})
        category_id = f"ref_{category_key}"
        if any(category.get("id") == category_id for category in schema.get("categories", [])):
            continue
        title = category_meta.get("title") or category_key.replace("_", " ").title()
        schema["categories"].append(
            {
                "id": category_id,
                "file": "atak_pref_reference",
                "title": title,
                "source": "atak_pref_reference",
                "sections": [
                    {
                        "title": "Preferences",
                        "key": category_key,
                        "fields": [reference_field_to_schema_field(ref) for ref in refs],
                    }
                ],
                "fields": [],
            }
        )


def enrich_schema(schema: dict[str, Any], reference: dict[str, Any] | None = None) -> dict[str, Any]:
    reference = reference or load_reference()
    enriched = copy.deepcopy(schema)
    ref_keys = reference.get("keys", {})

    for _, _, field in iter_schema_fields(enriched):
        ref_key, ref = resolve_reference_key(field["key"], ref_keys)
        if ref:
            apply_reference_to_field(field, ref, canonical_key=ref_key)
        else:
            mark_non_exportable_navigation_fields(field)

    add_missing_reference_categories(enriched, reference)

    base_categories = [
        category for category in enriched.get("categories", []) if category.get("source") != "atak_pref_reference"
    ]
    reference_categories = [
        category for category in enriched.get("categories", []) if category.get("source") == "atak_pref_reference"
    ]
    enriched["categories"] = base_categories + reference_categories

    enriched.setdefault("reference", {})
    enriched["reference"]["atak_core"] = {
        "source": reference.get("source"),
        "sheet": reference.get("sheet"),
        "stats": reference.get("stats", {}),
    }
    return apply_watchtower_enrichment(enriched, reference=reference)
