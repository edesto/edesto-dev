"""Tests for the ESP-IDF toolchain."""

from pathlib import Path
from unittest.mock import patch

import pytest
from edesto_dev.toolchains.espidf import EspIdfToolchain
from edesto_dev.toolchain import Board


@pytest.fixture
def espidf():
    return EspIdfToolchain()


class TestEspIdfBasics:
    def test_name(self, espidf):
        assert espidf.name == "espidf"

    def test_detect_project_with_sdkconfig(self, espidf, tmp_path):
        (tmp_path / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.16)")
        (tmp_path / "sdkconfig").write_text("")
        assert espidf.detect_project(tmp_path) is True

    def test_detect_project_with_main_dir(self, espidf, tmp_path):
        (tmp_path / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.16)")
        main = tmp_path / "main"
        main.mkdir()
        (main / "CMakeLists.txt").write_text("idf_component_register()")
        assert espidf.detect_project(tmp_path) is True

    def test_no_project(self, espidf, tmp_path):
        assert espidf.detect_project(tmp_path) is False

    def test_cmake_alone_not_enough(self, espidf, tmp_path):
        (tmp_path / "CMakeLists.txt").write_text("project(myapp)")
        assert espidf.detect_project(tmp_path) is False

    def test_compile_command(self, espidf):
        board = Board(slug="esp32", name="ESP32", baud_rate=115200)
        assert espidf.compile_command(board) == "idf.py build"

    def test_upload_command(self, espidf):
        board = Board(slug="esp32", name="ESP32", baud_rate=115200)
        cmd = espidf.upload_command(board, "/dev/ttyUSB0")
        assert "idf.py" in cmd
        assert "/dev/ttyUSB0" in cmd
        assert "flash" in cmd

    def test_monitor_command(self, espidf):
        board = Board(slug="esp32", name="ESP32", baud_rate=115200)
        cmd = espidf.monitor_command(board, "/dev/ttyUSB0")
        assert "idf.py" in cmd
        assert "monitor" in cmd

    @patch("shutil.which", return_value="/usr/local/bin/idf.py")
    def test_doctor_ok(self, mock_which, espidf):
        result = espidf.doctor()
        assert result["ok"] is True

    @patch("shutil.which", return_value=None)
    def test_doctor_missing(self, mock_which, espidf):
        result = espidf.doctor()
        assert result["ok"] is False
