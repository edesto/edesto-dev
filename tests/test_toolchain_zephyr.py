"""Tests for the Zephyr toolchain."""

from pathlib import Path
from unittest.mock import patch

import pytest
from edesto_dev.toolchains.zephyr import ZephyrToolchain
from edesto_dev.toolchain import Board


@pytest.fixture
def zephyr():
    return ZephyrToolchain()


class TestZephyrBasics:
    def test_name(self, zephyr):
        assert zephyr.name == "zephyr"

    def test_detect_project_with_prj_conf(self, zephyr, tmp_path):
        (tmp_path / "prj.conf").write_text("CONFIG_GPIO=y")
        assert zephyr.detect_project(tmp_path) is True

    def test_detect_project_with_west_yml(self, zephyr, tmp_path):
        (tmp_path / "west.yml").write_text("manifest:\n  remotes:")
        assert zephyr.detect_project(tmp_path) is True

    def test_detect_project_with_cmake_zephyr(self, zephyr, tmp_path):
        (tmp_path / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.20)\nfind_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})\nproject(myapp)"
        )
        assert zephyr.detect_project(tmp_path) is True

    def test_no_project(self, zephyr, tmp_path):
        assert zephyr.detect_project(tmp_path) is False

    def test_cmake_without_zephyr_not_detected(self, zephyr, tmp_path):
        (tmp_path / "CMakeLists.txt").write_text("project(myapp)")
        assert zephyr.detect_project(tmp_path) is False


class TestZephyrCommands:
    def test_compile_command(self, zephyr):
        board = Board(slug="nrf52840dk_nrf52840", name="nRF52840 DK", baud_rate=115200)
        cmd = zephyr.compile_command(board)
        assert "west build" in cmd
        assert "nrf52840dk_nrf52840" in cmd

    def test_upload_command(self, zephyr):
        board = Board(slug="nrf52840dk_nrf52840", name="nRF52840 DK", baud_rate=115200)
        cmd = zephyr.upload_command(board, "/dev/ttyACM0")
        assert cmd == "west flash"

    def test_monitor_command(self, zephyr):
        board = Board(slug="nrf52840dk_nrf52840", name="nRF52840 DK", baud_rate=115200)
        cmd = zephyr.monitor_command(board, "/dev/ttyACM0")
        assert "/dev/ttyACM0" in cmd
        assert "115200" in cmd


class TestZephyrDoctor:
    @patch("shutil.which", return_value="/usr/local/bin/west")
    def test_doctor_ok(self, mock_which, zephyr):
        result = zephyr.doctor()
        assert result["ok"] is True

    @patch("shutil.which", return_value=None)
    def test_doctor_missing(self, mock_which, zephyr):
        result = zephyr.doctor()
        assert result["ok"] is False
