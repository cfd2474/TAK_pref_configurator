"""Apply Watchtower MDM ATAK Settings metadata to the UI schema."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

WATCHTOWER_PATH = Path(__file__).resolve().parent.parent / "data" / "watchtower_atak_settings.json"

NON_EXPORTABLE_KEYS = frozenset({"savePrefs", "loadPrefs", "loadPartialPrefs"})

WATCHTOWER_KEY_ALIASES = {
    "atakRoleTypeAction": "atakRoleType",
    "locationUnitTypeAction": "locationUnitType",
}

TRISTATE_OPTIONS = [
    {"label": "— Not set —", "value": ""},
    {"label": "Off", "value": "false"},
    {"label": "On", "value": "true"},
]


def load_watchtower(path: Path | None = None) -> dict[str, Any]:
    watchtower_path = path or WATCHTOWER_PATH
    if not watchtower_path.exists():
        return {"keys": {}, "stats": {}}
    with watchtower_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def resolve_watchtower_key(field_key: str, wt_keys: dict[str, Any]) -> tuple[str, dict[str, Any]] | tuple[None, None]:
    if field_key in wt_keys:
        return field_key, wt_keys[field_key]

    alias = WATCHTOWER_KEY_ALIASES.get(field_key)
    if alias and alias in wt_keys:
        return alias, wt_keys[alias]

    if field_key.endswith("Action"):
        candidate = field_key[: -len("Action")]
        if candidate in wt_keys:
            return candidate, wt_keys[candidate]

    return None, None


def _watchtower_select_options(options: list[str]) -> list[dict[str, str]]:
    mapped: list[dict[str, str]] = []
    for option in options:
        if option.lower() in {"unset", "not set"}:
            continue
        mapped.append({"label": option, "value": option})
    return mapped


def _apply_tristate(field: dict[str, Any]) -> None:
    field["type"] = "boolean"
    field["input"] = "tristate"
    field["options"] = list(TRISTATE_OPTIONS)
    field["storage_type"] = "boolean"
    if not field.get("java_class"):
        field["java_class"] = "class java.lang.Boolean"


def _apply_select(field: dict[str, Any], options: list[dict[str, str]]) -> None:
    field["type"] = "select"
    field["input"] = "select"
    field["options"] = options
    if not field.get("storage_type"):
        field["storage_type"] = "string"


def _reference_select_options(ref: dict[str, Any]) -> list[dict[str, str]]:
    return [{"label": opt["label"], "value": str(opt["value"])} for opt in ref.get("options", [])]


def _clean_watchtower_description(description: str) -> str:
    text = description.strip()
    text = re.sub(r"\s*\.\.\.\s*Read More\s*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*Read More\s*$", "", text, flags=re.IGNORECASE)
    return text.strip()


def _is_truncated_watchtower_description(description: str) -> bool:
    if re.search(r"\.\.\.|Read More", description, flags=re.IGNORECASE):
        return True
    text = description.strip()
    if not text:
        return False
    if text[-1] in ".!?\"'":
        return False
    # Watchtower MDM preview text is capped around 48 characters without ellipsis.
    return len(text) >= 40


def _choose_field_summary(existing_summary: str, watchtower_description: str) -> str:
    existing = (existing_summary or "").strip()
    cleaned = _clean_watchtower_description(watchtower_description)
    if not cleaned:
        return existing
    if _is_truncated_watchtower_description(watchtower_description):
        if existing and (
            len(existing) > len(cleaned)
            or existing[-1] in ".!?\"'"
        ):
            return existing
        return existing
    if len(cleaned) > len(existing):
        return cleaned
    return existing or cleaned


def apply_watchtower_to_field(
    field: dict[str, Any],
    wt: dict[str, Any],
    ref: dict[str, Any] | None = None,
) -> None:
    ref = ref or {}

    if wt.get("title"):
        field["title"] = wt["title"]
    if wt.get("description"):
        field["summary"] = _choose_field_summary(field.get("summary") or "", wt["description"])

    wt_type = wt.get("inputType")
    ref_options = _reference_select_options(ref) if ref.get("options") else []

    if wt_type == "tristate_boolean" or (wt_type == "text" and ref.get("type") == "boolean"):
        _apply_tristate(field)
    elif wt_type == "select":
        options = _watchtower_select_options(wt.get("options", []))
        if len(options) >= 2:
            _apply_select(field, options)
        elif len(ref_options) >= 2:
            _apply_select(field, ref_options)
    elif wt_type == "number":
        field["type"] = ref.get("type") if ref.get("type") in {"integer", "float", "string"} else "integer"
        field.pop("input", None)
        field.pop("options", None)
    elif wt_type == "text":
        if len(ref_options) >= 2:
            _apply_select(field, ref_options)
        elif ref.get("type") == "boolean":
            _apply_tristate(field)
        else:
            field["type"] = ref.get("type", "string")
            field.pop("input", None)
            field.pop("options", None)

    field["watchtower"] = True


def apply_watchtower_enrichment(
    schema: dict[str, Any],
    watchtower: dict[str, Any] | None = None,
    reference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from .schema_enricher import iter_schema_fields, resolve_reference_key

    watchtower = watchtower or load_watchtower()
    wt_keys = watchtower.get("keys", {})
    ref_keys = (reference or {}).get("keys", {})
    enriched = copy.deepcopy(schema)

    for _, _, field in iter_schema_fields(enriched):
        wt_key, wt = resolve_watchtower_key(field["key"], wt_keys)
        if not wt:
            continue

        ref_key, ref = resolve_reference_key(field["key"], ref_keys)
        apply_watchtower_to_field(field, wt, ref or {})

        if wt_key in NON_EXPORTABLE_KEYS:
            field["exportable"] = False

    enriched.setdefault("reference", {})
    enriched["reference"]["watchtower"] = {
        "source": watchtower.get("source"),
        "pages": watchtower.get("pages"),
        "stats": watchtower.get("stats", {}),
    }
    return enriched
