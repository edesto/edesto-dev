"""Tests for the custom/TOML toolchain."""

import pytest
from edesto_dev.toolchains.custom import CustomToolchain
from edesto_dev.toolchain import Board


@pytest.fixture
def custom():
    return CustomToolchain(
        compile_cmd="make build",
        upload_cmd="make flash PORT={port}",
        baud_rate=115200,
    )


class TestCustomToolchain:
    def test_name(self, custom):
        assert custom.name == "custom"

    def test_compile_command(self, custom):
        board = Board(slug="myboard", name="My Board", baud_rate=115200)
        assert custom.compile_command(board) == "make build"

    def test_upload_command_interpolates_port(self, custom):
        board = Board(slug="myboard", name="My Board", baud_rate=115200)
        cmd = custom.upload_command(board, "/dev/ttyUSB0")
        assert cmd == "make flash PORT=/dev/ttyUSB0"

    def test_detect_project_always_false(self, custom, tmp_path):
        assert custom.detect_project(tmp_path) is False

    def test_serial_config(self, custom):
        board = Board(slug="myboard", name="My Board", baud_rate=115200)
        config = custom.serial_config(board)
        assert config["baud_rate"] == 115200

    def test_board_info_empty(self, custom):
        board = Board(slug="myboard", name="My Board", baud_rate=115200)
        assert custom.board_info(board) == {}
