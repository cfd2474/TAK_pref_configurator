"""Tests for preference XML extraction."""

from backend.app.preference_extract import extract_category_from_xml, infer_field, parse_strings_xml
import xml.etree.ElementTree as ET

ANDROID_NS = "{http://schemas.android.com/apk/res/android}"

SAMPLE_PREFS = b"""<?xml version="1.0" encoding="utf-8"?>
<PreferenceScreen xmlns:android="http://schemas.android.com/apk/res/android">
  <PreferenceCategory android:title="Network">
    <CheckBoxPreference
      android:key="enableMesh"
      android:title="@string/enable_mesh"
      android:defaultValue="true" />
    <ListPreference
      android:key="hopLimit"
      android:title="Hop Limit"
      android:entries="@array/hop_entries"
      android:entryValues="@array/hop_values"
      android:defaultValue="3" />
  </PreferenceCategory>
</PreferenceScreen>
"""


def test_parse_strings_xml():
    xml = b'<resources><string name="enable_mesh">Enable Mesh</string></resources>'
    assert parse_strings_xml(xml)["enable_mesh"] == "Enable Mesh"


def test_extract_category_from_xml():
    strings = {"enable_mesh": "Enable Mesh"}
    arrays = {
        "hop_entries": ["1", "3", "5"],
        "hop_values": ["1", "3", "5"],
    }
    category = extract_category_from_xml(
        SAMPLE_PREFS,
        source_name="preferences.xml",
        category_id="plugin_test",
        title="Test Plugin Preferences",
        strings=strings,
        arrays=arrays,
    )
    assert category is not None
    assert category["id"] == "plugin_test"
    assert len(category["sections"]) == 1
    fields = category["sections"][0]["fields"]
    assert fields[0]["key"] == "enableMesh"
    assert fields[0]["type"] == "boolean"
    assert fields[1]["key"] == "hopLimit"
    assert fields[1]["type"] == "select"
    assert len(fields[1]["options"]) == 3


def test_infer_field_skips_without_key():
    elem = ET.Element(f"{ANDROID_NS}PreferenceScreen")
    field = infer_field(elem, {}, {})
    assert field["key"] == ""
