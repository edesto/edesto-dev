"""Tests for toolchain base class."""

import pytest
from edesto_dev.toolchain import Toolchain, Board


class TestBoard:
    def test_board_has_required_fields(self):
        board = Board(
            slug="test-board",
            name="Test Board",
            baud_rate=115200,
        )
        assert board.slug == "test-board"
        assert board.name == "Test Board"
        assert board.baud_rate == 115200
        assert board.capabilities == []
        assert board.pins == {}
        assert board.pitfalls == []
        assert board.pin_notes == []

    def test_board_with_all_fields(self):
        board = Board(
            slug="full-board",
            name="Full Board",
            baud_rate=9600,
            capabilities=["wifi"],
            pins={"led": 13},
            pitfalls=["Watch out"],
            pin_notes=["GPIO 13: LED"],
        )
        assert board.capabilities == ["wifi"]
        assert board.pins == {"led": 13}


class TestToolchainABC:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            Toolchain()

    def test_has_required_abstract_methods(self):
        abstract_methods = Toolchain.__abstractmethods__
        assert "name" in abstract_methods
        assert "detect_project" in abstract_methods
        assert "detect_boards" in abstract_methods
        assert "compile_command" in abstract_methods
        assert "upload_command" in abstract_methods
        assert "serial_config" in abstract_methods
        assert "board_info" in abstract_methods
