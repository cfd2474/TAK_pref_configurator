"""Tests for deployable pref session-key handling."""

from __future__ import annotations

from backend.app.session_prefs import (
    analyze_session_pref_issues,
    repair_radial_menu_preferences,
    strip_session_preferences,
)


def test_analyze_detects_location_unit_type_conflict() -> None:
    preferences = {
        "locationUnitType": {"type": "string", "value": "a-f-G-U-C"},
        "lastCoTTypeSet": {"type": "string", "value": "a-u-G"},
        "lastIconsetPath": {"type": "string", "value": "COT_MAPPING_2525C/a-u/a-u-G"},
    }
    analysis = analyze_session_pref_issues(preferences)
    assert analysis["unit_type_conflict"] is True
    assert len(analysis["session_keys"]) == 2
    assert any("Not Recognized" in warning for warning in analysis["warnings"])


def test_strip_session_preferences_removes_iconset_session_keys() -> None:
    preferences = {
        "locationUnitType": {"type": "string", "value": "a-f-G-U-C"},
        "lastCoTTypeSet": {"type": "string", "value": "a-u-G"},
        "locationTeam": {"type": "string", "value": "Cyan"},
    }
    cleaned, stripped = strip_session_preferences(preferences)
    assert "lastCoTTypeSet" not in cleaned
    assert "locationUnitType" in cleaned
    assert "locationTeam" in cleaned
    assert stripped == ["lastCoTTypeSet"]


def test_repair_radial_menu_preferences_cleans_conflict() -> None:
    preferences = {
        "locationUnitType": {"type": "string", "value": "a-f-G-U-C"},
        "lastCoTTypeSet": {"type": "string", "value": "a-u-G"},
        "lastIconsetPath": {"type": "string", "value": "COT_MAPPING_2525C/a-u/a-u-G"},
        "locationTeam": {"type": "string", "value": "Cyan"},
    }
    result = repair_radial_menu_preferences(preferences)
    assert result["repaired"] is True
    assert "lastCoTTypeSet" not in result["preferences"]
    assert "lastIconsetPath" not in result["preferences"]
    assert result["preferences"]["locationUnitType"]["value"] == "a-f-G-U-C"
    assert result["unit_type_kept"] == "a-f-G-U-C"
    assert len(result["stripped"]) == 2
    assert any("My Display Type" in message for message in result["messages"])


def test_repair_radial_menu_preferences_noop_when_clean() -> None:
    preferences = {
        "locationUnitType": {"type": "string", "value": "a-f-G-U-C"},
        "locationTeam": {"type": "string", "value": "Cyan"},
    }
    result = repair_radial_menu_preferences(preferences)
    assert result["repaired"] is False
    assert result["stripped"] == []
    assert result["messages"] == []
