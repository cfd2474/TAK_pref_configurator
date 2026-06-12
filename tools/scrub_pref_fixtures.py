#!/usr/bin/env python3
"""Scrub sensitive values from .pref fixture files before commit."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

GOOGLE_API_KEY = re.compile(rb"AIzaSy[A-Za-z0-9_-]{20,}")


def scrub_bytes(data: bytes) -> bytes:
    return GOOGLE_API_KEY.sub(b"REDACTED", data)


def main() -> int:
    changed = 0
    for path in (ROOT / "tests" / "fixtures").glob("*.pref"):
        original = path.read_bytes()
        scrubbed = scrub_bytes(original)
        if scrubbed != original:
            path.write_bytes(scrubbed)
            changed += 1
            print(f"Scrubbed {path.name}")
    print(f"Done. {changed} file(s) updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
