"""Tests for the MicroPython toolchain."""

from pathlib import Path
from unittest.mock import patch

import pytest
from edesto_dev.toolchains.micropython import MicroPythonToolchain
from edesto_dev.toolchain import Board


@pytest.fixture
def mp():
    return MicroPythonToolchain()


class TestMicroPythonBasics:
    def test_name(self, mp):
        assert mp.name == "micropython"

    def test_detect_project_boot_py(self, mp, tmp_path):
        (tmp_path / "boot.py").write_text("")
        assert mp.detect_project(tmp_path) is True

    def test_detect_project_main_py(self, mp, tmp_path):
        (tmp_path / "main.py").write_text("")
        assert mp.detect_project(tmp_path) is True

    def test_no_project(self, mp, tmp_path):
        assert mp.detect_project(tmp_path) is False

    def test_ino_files_not_detected_as_micropython(self, mp, tmp_path):
        (tmp_path / "main.py").write_text("")
        (tmp_path / "sketch.ino").write_text("")
        assert mp.detect_project(tmp_path) is False

    def test_compile_is_noop(self, mp):
        board = Board(slug="esp32", name="ESP32", baud_rate=115200)
        cmd = mp.compile_command(board)
        assert "No compile" in cmd or "no compile" in cmd.lower()

    def test_upload_uses_mpremote(self, mp):
        board = Board(slug="esp32", name="ESP32", baud_rate=115200)
        cmd = mp.upload_command(board, "/dev/ttyUSB0")
        assert "mpremote" in cmd
        assert "/dev/ttyUSB0" in cmd

    def test_monitor_uses_repl(self, mp):
        board = Board(slug="esp32", name="ESP32", baud_rate=115200)
        cmd = mp.monitor_command(board, "/dev/ttyUSB0")
        assert "repl" in cmd

    @patch("shutil.which", return_value="/usr/local/bin/mpremote")
    def test_doctor_ok(self, mock_which, mp):
        result = mp.doctor()
        assert result["ok"] is True

    @patch("shutil.which", return_value=None)
    def test_doctor_missing(self, mock_which, mp):
        result = mp.doctor()
        assert result["ok"] is False

    def test_scaffold_creates_files(self, mp, tmp_path):
        board = Board(slug="esp32", name="ESP32", baud_rate=115200)
        mp.scaffold(board, tmp_path)
        assert (tmp_path / "boot.py").exists()
        assert (tmp_path / "main.py").exists()
