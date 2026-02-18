"""Tests for the PlatformIO toolchain."""

from pathlib import Path
from unittest.mock import patch

import pytest
from edesto_dev.toolchains.platformio import PlatformIOToolchain
from edesto_dev.toolchain import Board


@pytest.fixture
def pio():
    return PlatformIOToolchain()


class TestPlatformIOBasics:
    def test_name(self, pio):
        assert pio.name == "platformio"

    def test_detect_project(self, pio, tmp_path):
        (tmp_path / "platformio.ini").write_text("[env:esp32dev]")
        assert pio.detect_project(tmp_path) is True

    def test_no_project(self, pio, tmp_path):
        assert pio.detect_project(tmp_path) is False

    def test_compile_command(self, pio):
        board = Board(slug="esp32dev", name="ESP32", baud_rate=115200)
        assert pio.compile_command(board) == "pio run"

    def test_upload_command(self, pio):
        board = Board(slug="esp32dev", name="ESP32", baud_rate=115200)
        cmd = pio.upload_command(board, "/dev/ttyUSB0")
        assert "pio run" in cmd
        assert "--target upload" in cmd
        assert "/dev/ttyUSB0" in cmd

    def test_monitor_command(self, pio):
        board = Board(slug="esp32dev", name="ESP32", baud_rate=115200)
        cmd = pio.monitor_command(board, "/dev/ttyUSB0")
        assert "pio device monitor" in cmd

    @patch("shutil.which", return_value="/usr/local/bin/pio")
    def test_doctor_ok(self, mock_which, pio):
        result = pio.doctor()
        assert result["ok"] is True

    @patch("shutil.which", return_value=None)
    def test_doctor_missing(self, mock_which, pio):
        result = pio.doctor()
        assert result["ok"] is False

    def test_serial_config(self, pio):
        board = Board(slug="esp32dev", name="ESP32", baud_rate=115200)
        config = pio.serial_config(board)
        assert config["baud_rate"] == 115200
        assert config["boot_delay"] == 3
