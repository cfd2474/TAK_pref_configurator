"""Tests for pasted XML import parsing."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from backend.app.main import _parse_pref_content

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_parse_text_content_matches_file_import() -> None:
    content = (FIXTURES / "cfd-basic-pref-4-25.pref").read_text(encoding="utf-8")
    parsed = _parse_pref_content(content)
    assert parsed["preference_name"] == "com.atakmap.app.civ_preferences"
    assert "nav_orientation_right" in parsed["preferences"]
    assert parsed["connections"]["cot_streams"] is not None


def test_parse_text_rejects_empty_content() -> None:
    with pytest.raises(HTTPException) as exc:
        _parse_pref_content("   ")
    assert exc.value.status_code == 400


def test_parse_text_rejects_invalid_xml() -> None:
    with pytest.raises(HTTPException) as exc:
        _parse_pref_content("<not-pref-xml>")
    assert exc.value.status_code == 400
