"""Tests for APK scanning and temp-file cleanup."""

from __future__ import annotations

import os

import pytest

from backend.app.apk_scanner import ApkScanError, scan_apk_bytes, scan_apk_path


def test_scan_apk_bytes_deletes_temp_file(monkeypatch):
    seen_paths: list[str] = []

    def fake_scan(path: str) -> dict:
        seen_paths.append(path)
        assert os.path.exists(path)
        return {"category": {"id": "plugin_test"}}

    monkeypatch.setattr("backend.app.apk_scanner.scan_apk_path", fake_scan)

    result = scan_apk_bytes(b"PK\x03\x04" + b"0" * 64, original_filename="sample.apk")
    assert result["category"]["id"] == "plugin_test"
    assert seen_paths
    assert not os.path.exists(seen_paths[0])


def test_scan_apk_bytes_rejects_non_zip():
    with pytest.raises(ApkScanError, match="not a valid APK"):
        scan_apk_bytes(b"not-a-zip")


def test_scan_apk_bytes_rejects_empty():
    with pytest.raises(ApkScanError, match="not a valid APK"):
        scan_apk_bytes(b"")


def test_scan_apk_path_invalid_file(tmp_path):
    bad_apk = tmp_path / "bad.apk"
    bad_apk.write_bytes(b"PK\x03\x04invalid")
    with pytest.raises(ApkScanError, match="Invalid APK"):
        scan_apk_path(str(bad_apk))


def test_scan_apk_path_no_preferences(tmp_path, monkeypatch):
    class FakeApk:
        def get_files(self):
            return ["AndroidManifest.xml"]

        def get_file(self, _path):
            return b""

        def get_package(self):
            return "com.example.plugin"

        def get_app_name(self):
            return "Example Plugin"

        def get_all_dex(self):
            return []

        def get_android_resources(self):
            raise RuntimeError("no resources")

    monkeypatch.setattr("backend.app.apk_scanner.APK", lambda _path: FakeApk())

    apk_path = tmp_path / "empty.apk"
    apk_path.write_bytes(b"PK\x03\x04")

    with pytest.raises(ApkScanError, match="No preference XML"):
        scan_apk_path(str(apk_path))
