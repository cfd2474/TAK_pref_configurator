"""Redact sensitive preference keys from imports, exports, and fixtures."""

from __future__ import annotations

import re
from typing import Any

REDACTED = "REDACTED"

SENSITIVE_PREF_KEYS = frozenset(
    {
        "vns_google_api_key",
        "caPassword",
        "clientPassword",
    }
)

SENSITIVE_KEY_PATTERNS = (
    re.compile(r".*_api_key$", re.IGNORECASE),
    re.compile(r".*apikey$", re.IGNORECASE),
    re.compile(r".*password$", re.IGNORECASE),
    re.compile(r".*secret$", re.IGNORECASE),
    re.compile(r".*token$", re.IGNORECASE),
)


def is_sensitive_key(key: str) -> bool:
    if key in SENSITIVE_PREF_KEYS:
        return True
    return any(pattern.match(key) for pattern in SENSITIVE_KEY_PATTERNS)


def redact_preferences(preferences: dict[str, Any]) -> dict[str, Any]:
    """Remove sensitive keys from a preferences map."""
    return {key: value for key, value in preferences.items() if not is_sensitive_key(key)}


def scrub_pref_xml(content: str) -> str:
    """Replace sensitive entry values in raw .pref XML."""
    scrubbed = content
    for key in SENSITIVE_PREF_KEYS:
        pattern = (
            rf'(<entry key="{re.escape(key)}" class="class java\.lang\.String">)'
            rf"[^<]*"
            rf"(</entry>)"
        )
        scrubbed = re.sub(pattern, rf"\1{REDACTED}\2", scrubbed)
    return scrubbed
