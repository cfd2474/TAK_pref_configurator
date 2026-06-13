"""Apply ATAK Core preference reference metadata to the UI schema."""

from __future__ import annotations

import copy
import json
import re
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

# ATAK boolean prefs where the xlsx lists True/False but the UI is a semantic switch.
BOOLEAN_OPTION_LABEL_OVERRIDES: dict[str, list[dict[str, str]]] = {
    "nav_orientation_right": [
        {"label": "Left", "value": "false"},
        {"label": "Right", "value": "true"},
    ],
    "landscape_extended_buttons": [
        {"label": "Disabled", "value": "false"},
        {"label": "Enabled", "value": "true"},
    ],
}

NON_EXPORTABLE_MENU_LAUNCHERS = frozenset({"my_location_icon_color", "my_actionbar_settings"})

ADJUST_TOOLBAR_SECTION_KEY = "adjust_toolbar_preferences_category"

GPS_ICON_COLOR_MODE_FIELD: dict[str, Any] = {
    "key": "gps_icon_color_mode",
    "title": "Self Icon Color Mode",
    "summary": "Choose whether the self icon uses default colors, your team color, or custom colors.",
    "type": "select",
    "input": "gps_icon_color_mode",
    "options": [
        {"label": "Default", "value": "default"},
        {"label": "Team color", "value": "team"},
        {"label": "Custom colors", "value": "custom"},
    ],
    "exportable": True,
}

TOOLBAR_MENU_EXPANSIONS: list[tuple[str, str, list[str]]] = [
    (
        "My Location Color / Size",
        "my_location_icon_color_fields",
        [
            "location_marker_scale_key",
            "gps_icon_color_mode",
            "custom_color_selected",
            "custom_outline_color_selected",
        ],
    ),
    (
        "Tool Bar Customization",
        "my_actionbar_settings_fields",
        [
            "nav_orientation_right",
            "actionbar_icon_color_key",
            "actionbar_background_color_key",
            "landscape_extended_buttons",
        ],
    ),
]

HIDDEN_NAV_CATEGORY_IDS = frozenset(
    {
        "call_sign_preference",
        "custom_actionbar_preferences",
        "ref_color_category",
        "ref_size_category",
    }
)

CATEGORY_TITLE_OVERRIDES = {
    "device_preferences": "Device/Callsign Preferences",
    "geocoder_preference_fragment": "GeoCoder Preference",
    "lrf_preferences": "LRF Preferences",
    "missionpackage_preferences": "Mission Package Preferences",
    "off_scr_indi_preferences": "Off Screen Indicator Preferences",
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
    _apply_color_field_metadata(field, ref)
    _apply_boolean_option_label_overrides(field)
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

    _apply_color_field_metadata(field, ref)
    _apply_boolean_option_label_overrides(field)


def _apply_boolean_option_label_overrides(field: dict[str, Any]) -> None:
    overrides = BOOLEAN_OPTION_LABEL_OVERRIDES.get(field["key"])
    if not overrides:
        return
    field["options"] = overrides
    field["type"] = "boolean"
    field["input"] = "select"
    field["storage_type"] = "boolean"
    if not field.get("java_class"):
        field["java_class"] = "class java.lang.Boolean"


def _apply_color_field_metadata(field: dict[str, Any], ref: dict[str, Any]) -> None:
    hint = ref.get("reference_hint") or ""
    if hint == "-1 through -16777216":
        field["input"] = "color"
        field["color_format"] = "android_int"
        if field.get("summary") in {hint, ""}:
            field["summary"] = "Pick a color or enter an Android ARGB integer (e.g. -256 for yellow)."
    elif hint == "16-bit Hexadecimal Color":
        field["input"] = "color"
        field["color_format"] = "hex"
        if field.get("summary") in {hint, ""}:
            field["summary"] = "Pick a color or enter a hex value (#RRGGBB)."


def mark_non_exportable_navigation_fields(field: dict[str, Any]) -> None:
    if field.get("options") or field.get("exportable") is False:
        return
    if field["key"] in NON_EXPORTABLE_MENU_LAUNCHERS:
        field["exportable"] = False
        return
    widget = field.get("widget", "")
    if field["key"].endswith("Action") or widget == "Preference" or widget.endswith("PanPreference"):
        field["exportable"] = False


def _reference_field_from_key(key: str, ref_keys: dict[str, Any]) -> dict[str, Any] | None:
    ref = ref_keys.get(key)
    if not ref:
        return None
    field = reference_field_to_schema_field(ref)
    apply_reference_to_field(field, ref)
    return field


def _find_schema_field(schema: dict[str, Any], key: str) -> dict[str, Any] | None:
    for _, _, field in iter_schema_fields(schema):
        if field["key"] == key:
            return copy.deepcopy(field)
    return None


def expand_adjust_toolbar_sections(schema: dict[str, Any], reference: dict[str, Any]) -> None:
    ref_keys = reference.get("keys", {})
    display = next((category for category in schema.get("categories", []) if category.get("id") == "display_preferences"), None)
    if not display:
        return

    new_sections: list[dict[str, Any]] = []
    replaced = False
    for section in display.get("sections", []):
        if section.get("key") != ADJUST_TOOLBAR_SECTION_KEY:
            new_sections.append(section)
            continue

        replaced = True
        for title, section_key, field_keys in TOOLBAR_MENU_EXPANSIONS:
            fields: list[dict[str, Any]] = []
            for key in field_keys:
                if key == "gps_icon_color_mode":
                    fields.append(copy.deepcopy(GPS_ICON_COLOR_MODE_FIELD))
                    continue
                ref_field = _reference_field_from_key(key, ref_keys)
                if ref_field:
                    if key == "custom_color_selected":
                        ref_field["title"] = "Custom Icon Fill Color"
                        ref_field["summary"] = "Main fill color when Self Icon Color Mode is set to Custom colors."
                    elif key == "custom_outline_color_selected":
                        ref_field["title"] = "Custom Icon Outline Color"
                        ref_field["summary"] = "Outline color when Self Icon Color Mode is set to Custom colors."
                    elif key == "location_marker_scale_key":
                        ref_field["summary"] = "Size of the self-location marker on the map."
                    elif key == "actionbar_icon_color_key":
                        ref_field["summary"] = "Toolbar icon tint color."
                    elif key == "actionbar_background_color_key":
                        ref_field["summary"] = "Toolbar background color (rendered with transparency on device)."
                    fields.append(ref_field)
                    continue
                schema_field = _find_schema_field(schema, key)
                if schema_field:
                    fields.append(schema_field)
            new_sections.append({"title": title, "key": section_key, "fields": fields})

    if replaced:
        display["sections"] = new_sections


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


def apply_category_nav_overrides(schema: dict[str, Any]) -> None:
    for category in schema.get("categories", []):
        category_id = category.get("id")
        if category_id in HIDDEN_NAV_CATEGORY_IDS:
            category["nav_hidden"] = True
        if category_id in CATEGORY_TITLE_OVERRIDES:
            category["title"] = CATEGORY_TITLE_OVERRIDES[category_id]


_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def _is_hex_color(value: str) -> bool:
    return bool(_HEX_COLOR_RE.match(value))


def apply_palette_color_fields(schema: dict[str, Any]) -> None:
    for _, _, field in iter_schema_fields(schema):
        options = field.get("options") or []
        hex_options = [option for option in options if _is_hex_color(str(option.get("value", "")))]
        if len(hex_options) < 2:
            continue
        field["input"] = "palette_color"
        field["type"] = "select"


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

    expand_adjust_toolbar_sections(enriched, reference)

    enriched.setdefault("reference", {})
    enriched["reference"]["atak_core"] = {
        "source": reference.get("source"),
        "sheet": reference.get("sheet"),
        "stats": reference.get("stats", {}),
    }
    apply_category_nav_overrides(enriched)
    enriched = apply_watchtower_enrichment(enriched, reference=reference)
    apply_palette_color_fields(enriched)
    return enriched
