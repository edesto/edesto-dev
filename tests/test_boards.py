"""Tests for board definitions."""

import pytest
from edesto_dev.boards import get_board, list_boards, BoardNotFoundError


class TestGetBoard:
    def test_esp32_returns_correct_fqbn(self):
        board = get_board("esp32")
        assert board.fqbn == "esp32:esp32:esp32"

    def test_esp32_has_name(self):
        board = get_board("esp32")
        assert board.name == "ESP32"

    def test_esp32_has_core(self):
        board = get_board("esp32")
        assert board.core == "esp32:esp32"

    def test_esp32_has_baud_rate(self):
        board = get_board("esp32")
        assert board.baud_rate == 115200

    def test_esp32_has_capabilities(self):
        board = get_board("esp32")
        assert "wifi" in board.capabilities
        assert "bluetooth" in board.capabilities

    def test_esp32_has_pins(self):
        board = get_board("esp32")
        assert "onboard_led" in board.pins
        assert board.pins["onboard_led"] == 2

    def test_esp32_has_pitfalls(self):
        board = get_board("esp32")
        assert len(board.pitfalls) > 0
        assert any("ADC2" in p for p in board.pitfalls)

    def test_unknown_board_raises(self):
        with pytest.raises(BoardNotFoundError):
            get_board("nonexistent")


class TestListBoards:
    def test_returns_list(self):
        boards = list_boards()
        assert isinstance(boards, list)
        assert len(boards) > 0

    def test_esp32_in_list(self):
        boards = list_boards()
        slugs = [b.slug for b in boards]
        assert "esp32" in slugs
