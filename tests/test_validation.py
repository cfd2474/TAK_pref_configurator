"""Tests for Watchtower-aligned connection validation."""

from backend.app.validation import validate_connections


def test_empty_connections_pass():
    assert validate_connections({}) == []


def test_connection_missing_description_and_connect_string():
    errors = validate_connections(
        {
            "cot_streams": [{"enabled": True}],
        }
    )
    assert len(errors) == 2
    assert "Description is required" in errors[0]
    assert "Connect string is required" in errors[1]


def test_valid_connection_passes():
    errors = validate_connections(
        {
            "cot_streams": [
                {
                    "description": "TAK Server",
                    "connectString": "ssl:tak.example.com:8089:stream",
                }
            ],
        }
    )
    assert errors == []
