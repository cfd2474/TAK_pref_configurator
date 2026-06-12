"""Scan ATAK plugin APKs for preference fields. APK bytes are never persisted."""

from __future__ import annotations

import os
import re
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

os.environ.setdefault("LOGURU_LEVEL", "ERROR")

from androguard.core.apk import APK
from androguard.core.axml import AXMLPrinter

from .pref_generator import DEFAULT_APP_PREFS
from .preference_extract import (
    count_fields,
    extract_category_from_xml,
    parse_arrays_xml,
    parse_strings_xml,
)

MAX_APK_BYTES = 100 * 1024 * 1024
PREF_XML_RE = re.compile(r"^res/(?:xml[^/]*/)?[^/]*(?:pref|preferences)[^/]*\.xml$", re.IGNORECASE)
SHORT_RES_XML_RE = re.compile(r"^res/[^/]+\.xml$", re.IGNORECASE)
STRINGS_XML_RE = re.compile(r"^res/values(?:-[^/]+)?/strings\.xml$", re.IGNORECASE)
ARRAYS_XML_RE = re.compile(r"^res/values(?:-[^/]+)?/arrays\.xml$", re.IGNORECASE)
PREF_GROUP_RE = re.compile(rb"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*){2,}_preferences", re.IGNORECASE)
PREFERENCE_MARKERS = (
    "PreferenceScreen",
    "CheckBoxPreference",
    "ListPreference",
    "EditTextPreference",
    "SwitchPreference",
    "MultiSelectListPreference",
    "SeekBarPreference",
    "PreferenceCategory",
)


class ApkScanError(Exception):
    """Raised when an uploaded APK cannot be scanned."""


def decode_resource_xml(data: bytes) -> bytes | None:
    if not data:
        return None
    stripped = data.lstrip()
    if stripped.startswith(b"<?xml") or stripped.startswith(b"<"):
        return data
    try:
        return AXMLPrinter(data).get_xml(pretty=False)
    except Exception:
        return None


def is_named_preference_xml(path: str) -> bool:
    return bool(PREF_XML_RE.match(path))


def looks_like_preference_xml(xml_bytes: bytes) -> bool:
    text = xml_bytes.decode("utf-8", errors="ignore")
    if "PreferenceScreen" in text:
        return True
    has_category = "PreferenceCategory" in text
    has_widget = any(marker in text for marker in PREFERENCE_MARKERS[1:])
    return has_category and has_widget


def discover_preference_xml(apk: APK) -> list[tuple[str, bytes]]:
    discovered: list[tuple[str, bytes]] = []
    seen_paths: set[str] = set()

    for path in apk.get_files():
        if path in seen_paths or path == "AndroidManifest.xml" or not path.endswith(".xml"):
            continue
        if not (is_named_preference_xml(path) or SHORT_RES_XML_RE.match(path) or "/xml/" in path):
            continue

        try:
            decoded = decode_resource_xml(apk.get_file(path))
        except Exception:
            continue
        if not decoded or not looks_like_preference_xml(decoded):
            continue

        seen_paths.add(path)
        discovered.append((path, decoded))

    return discovered


def load_strings_and_arrays(apk: APK) -> tuple[dict[str, str], dict[str, list[str]]]:
    strings: dict[str, str] = {}
    arrays: dict[str, list[str]] = {}

    try:
        arsc = apk.get_android_resources()
        package = apk.get_package()
        strings.update(parse_strings_xml(arsc.get_string_resources(package)))
    except Exception:
        pass

    for path in apk.get_files():
        if STRINGS_XML_RE.match(path):
            decoded = decode_resource_xml(apk.get_file(path))
            if decoded:
                strings.update(parse_strings_xml(decoded))
        elif ARRAYS_XML_RE.match(path):
            decoded = decode_resource_xml(apk.get_file(path))
            if decoded:
                arrays.update(parse_arrays_xml(decoded, strings))

    return strings, arrays


def read_plugin_metadata(apk: APK) -> dict[str, str | None]:
    package = apk.get_package() or "unknown.plugin"
    try:
        version = apk.get_androidversion_name()
    except Exception:
        version = None
    meta: dict[str, str | None] = {
        "name": None,
        "description": None,
        "package": package,
        "version": version,
    }

    for path in ("assets/plugin.xml", "plugin.xml"):
        try:
            root = ET.fromstring(apk.get_file(path))
        except Exception:
            continue

        for tag in ("name", "description"):
            if meta.get(tag):
                continue
            elem = root.find(f".//{tag}")
            if elem is None:
                continue
            value = (elem.get("value") or elem.text or "").strip()
            if value:
                meta[tag] = value

    if not meta["name"]:
        app_label = apk.get_app_name()
        meta["name"] = app_label or package
    return meta


def detect_preference_group(apk: APK) -> str:
    candidates: set[str] = set()

    for dex_data in apk.get_all_dex():
        if not dex_data:
            continue
        for match in PREF_GROUP_RE.finditer(dex_data):
            candidates.add(match.group(0).decode("utf-8", errors="ignore"))

    preferred = {DEFAULT_APP_PREFS, "com.atakmap.app_preferences"}
    for name in preferred:
        if name in candidates:
            return DEFAULT_APP_PREFS

    plugin_specific = sorted(
        name for name in candidates if "atakmap.app" not in name and name.endswith("_preferences")
    )
    if len(plugin_specific) == 1:
        return plugin_specific[0]

    return DEFAULT_APP_PREFS


def sanitize_category_id(package: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", package).strip("_").lower()
    return f"plugin_{slug or 'unknown'}"


def merge_categories(categories: list[dict]) -> dict:
    if not categories:
        raise ApkScanError("No preference fields found in APK")

    if len(categories) == 1:
        return categories[0]

    merged = {
        "id": categories[0]["id"],
        "file": ", ".join(category["file"] for category in categories),
        "title": categories[0]["title"],
        "sections": [],
        "fields": [],
    }
    for category in categories:
        merged["fields"].extend(category.get("fields", []))
        merged["sections"].extend(category.get("sections", []))
    return merged


def scan_apk_path(apk_path: str) -> dict[str, Any]:
    try:
        apk = APK(apk_path)
    except Exception as exc:
        raise ApkScanError(f"Invalid APK file: {exc}") from exc

    strings, arrays = load_strings_and_arrays(apk)
    metadata = read_plugin_metadata(apk)
    preference_group = detect_preference_group(apk)

    pref_files = discover_preference_xml(apk)
    if not pref_files:
        raise ApkScanError("No preference XML files found in APK")

    plugin_name = metadata.get("name") or metadata.get("package") or "Plugin"
    category_id = sanitize_category_id(str(metadata.get("package") or plugin_name))
    plugin_title = f"PLUGIN: {plugin_name}"

    categories: list[dict] = []
    for path, decoded in pref_files:
        category = extract_category_from_xml(
            decoded,
            source_name=path,
            category_id=category_id if len(pref_files) == 1 else f"{category_id}_{Path(path).stem}",
            title=plugin_title,
            strings=strings,
            arrays=arrays,
        )
        if category:
            category["source"] = "plugin_apk"
            category["plugin_package"] = metadata.get("package")
            categories.append(category)

    if not categories:
        raise ApkScanError("Preference XML files were found but no fields could be extracted")

    category = merge_categories(categories)
    category["id"] = category_id
    category["title"] = plugin_title

    field_count = count_fields(category)
    pref_paths = [path for path, _ in pref_files]
    return {
        "plugin": metadata,
        "preference_group": preference_group,
        "category": category,
        "stats": {
            "field_count": field_count,
            "source_files": pref_paths,
        },
        "warnings": [
            "Only preferences declared in res/xml are included; code-only settings may be missing.",
            "NWSharedPreferences and other custom stores are not scanned from APK.",
        ],
    }


def scan_apk_bytes(content: bytes, *, original_filename: str | None = None) -> dict[str, Any]:
    """Decode an uploaded APK from a temporary file, then delete it immediately."""
    if len(content) > MAX_APK_BYTES:
        raise ApkScanError(f"APK exceeds maximum size of {MAX_APK_BYTES // (1024 * 1024)} MB")

    if not content.startswith(b"PK"):
        raise ApkScanError("Upload is not a valid APK/ZIP archive")

    suffix = ".apk"
    if original_filename and original_filename.lower().endswith(".apk"):
        suffix = ".apk"

    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
            tmp_path = handle.name
            handle.write(content)
            handle.flush()

        return scan_apk_path(tmp_path)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
