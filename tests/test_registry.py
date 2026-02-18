"""Tests for toolchain registry."""

from edesto_dev.toolchains import get_toolchain, list_toolchains, register_toolchain
from edesto_dev.toolchain import Toolchain, Board, DetectedBoard
from pathlib import Path


class _DummyToolchain(Toolchain):
    """Minimal concrete toolchain for testing."""

    @property
    def name(self):
        return "dummy"

    def detect_project(self, path):
        return False

    def detect_boards(self):
        return []

    def compile_command(self, board):
        return "dummy compile"

    def upload_command(self, board, port):
        return "dummy upload"

    def serial_config(self, board):
        return {"baud_rate": 115200, "boot_delay": 3}

    def board_info(self, board):
        return {}


class TestRegistry:
    def test_register_and_get(self):
        tc = _DummyToolchain()
        register_toolchain(tc)
        assert get_toolchain("dummy") is tc

    def test_list_toolchains(self):
        tc = _DummyToolchain()
        register_toolchain(tc)
        names = [t.name for t in list_toolchains()]
        assert "dummy" in names

    def test_get_unknown_returns_none(self):
        assert get_toolchain("nonexistent_xyz") is None
