"""Tests for deployable pref session-key handling."""

from __future__ import annotations

from backend.app.session_prefs import (
    analyze_session_pref_issues,
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
