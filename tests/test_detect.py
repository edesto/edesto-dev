"""Tests for toolchain and board detection."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from edesto_dev.detect import detect_toolchain, detect_all_boards


class TestDetectToolchain:
    def test_detects_arduino_from_ino_file(self, tmp_path):
        (tmp_path / "sketch.ino").write_text("void setup() {}")
        tc = detect_toolchain(tmp_path)
        assert tc is not None
        assert tc.name == "arduino"

    def test_returns_none_for_empty_dir(self, tmp_path):
        tc = detect_toolchain(tmp_path)
        assert tc is None

    def test_returns_none_for_unrecognized_files(self, tmp_path):
        (tmp_path / "main.rs").write_text("fn main() {}")
        tc = detect_toolchain(tmp_path)
        assert tc is None


class TestDetectAllBoards:
    @patch("edesto_dev.toolchains.arduino.subprocess.run")
    def test_detects_boards_from_arduino(self, mock_run):
        import json
        mock = MagicMock()
        mock.stdout = json.dumps({
            "detected_ports": [{
                "matching_boards": [{"name": "ESP32", "fqbn": "esp32:esp32:esp32"}],
                "port": {"address": "/dev/ttyUSB0", "protocol": "serial"},
            }]
        })
        mock.returncode = 0
        mock_run.return_value = mock
        detected = detect_all_boards()
        assert len(detected) >= 1
        assert any(d.board.slug == "esp32" for d in detected)

    @patch("edesto_dev.toolchains.arduino.subprocess.run", side_effect=FileNotFoundError)
    def test_handles_toolchain_failure(self, mock_run):
        # Should not raise, just return empty/partial results
        detected = detect_all_boards()
        assert isinstance(detected, list)


class TestEdesToml:
    def test_edesto_toml_loads_custom_toolchain(self, tmp_path):
        toml_content = '[toolchain]\ncompile = "make build"\nupload = "make flash PORT={port}"\n\n[serial]\nbaud_rate = 9600\n'
        (tmp_path / "edesto.toml").write_text(toml_content)
        tc = detect_toolchain(tmp_path)
        assert tc is not None
        assert tc.name == "custom"

    def test_edesto_toml_takes_priority_over_ino(self, tmp_path):
        toml_content = '[toolchain]\ncompile = "make"\nupload = "make flash"\n'
        (tmp_path / "edesto.toml").write_text(toml_content)
        (tmp_path / "sketch.ino").write_text("void setup() {}")
        tc = detect_toolchain(tmp_path)
        assert tc.name == "custom"
