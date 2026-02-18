"""Tests for CLAUDE.md template rendering."""

import re

import pytest
from edesto_dev.boards import get_board, list_boards
from edesto_dev.templates import render_template


class TestRenderTemplate:
    def test_contains_board_name(self):
        board = get_board("esp32")
        result = render_template(board, port="/dev/ttyUSB0")
        assert "ESP32" in result

    def test_contains_fqbn(self):
        board = get_board("esp32")
        result = render_template(board, port="/dev/ttyUSB0")
        assert "esp32:esp32:esp32" in result

    def test_contains_port(self):
        board = get_board("esp32")
        result = render_template(board, port="/dev/ttyUSB0")
        assert "/dev/ttyUSB0" in result

    def test_no_unfilled_placeholders(self):
        board = get_board("esp32")
        result = render_template(board, port="/dev/ttyUSB0")
        placeholders = re.findall(r"\{[a-z_]+\}", result)
        assert placeholders == [], f"Unfilled placeholders: {placeholders}"

    def test_has_hardware_section(self):
        board = get_board("esp32")
        result = render_template(board, port="/dev/ttyUSB0")
        assert "## Hardware" in result

    def test_has_commands_section(self):
        board = get_board("esp32")
        result = render_template(board, port="/dev/ttyUSB0")
        assert "## Commands" in result
        assert "arduino-cli compile" in result
        assert "arduino-cli upload" in result

    def test_has_development_loop(self):
        board = get_board("esp32")
        result = render_template(board, port="/dev/ttyUSB0")
        assert "## Development Loop" in result
        assert "Compile" in result
        assert "Flash" in result
        assert "Validate" in result

    def test_has_serial_validation(self):
        board = get_board("esp32")
        result = render_template(board, port="/dev/ttyUSB0")
        assert "serial.Serial" in result
        assert "[READY]" in result
        assert "115200" in result

    def test_has_serial_conventions(self):
        board = get_board("esp32")
        result = render_template(board, port="/dev/ttyUSB0")
        assert "Serial.begin(115200)" in result
        assert "[READY]" in result
        assert "[ERROR]" in result
        assert "[SENSOR]" in result

    def test_has_board_specific_section(self):
        board = get_board("esp32")
        result = render_template(board, port="/dev/ttyUSB0")
        assert "Pin Reference" in result
        assert "Common Pitfalls" in result

    def test_has_pitfalls(self):
        board = get_board("esp32")
        result = render_template(board, port="/dev/ttyUSB0")
        assert "ADC2" in result

    def test_has_pin_notes(self):
        board = get_board("esp32")
        result = render_template(board, port="/dev/ttyUSB0")
        assert "GPIO 2: Onboard LED" in result

    def test_wifi_board_has_capabilities(self):
        board = get_board("esp32")
        result = render_template(board, port="/dev/ttyUSB0")
        assert "Capabilities" in result
        assert "#include <WiFi.h>" in result

    def test_non_wifi_board_no_wifi_includes(self):
        board = get_board("arduino-uno")
        result = render_template(board, port="/dev/ttyUSB0")
        assert "WiFi.h" not in result

    def test_has_datasheets_section(self):
        board = get_board("esp32")
        result = render_template(board, port="/dev/ttyUSB0")
        assert "## Datasheets" in result
        assert "datasheets/" in result
        assert ".pdf" in result.lower()


class TestAllBoardsRender:
    @pytest.mark.parametrize("slug", [b.slug for b in list_boards()])
    def test_renders_without_error(self, slug):
        board = get_board(slug)
        result = render_template(board, port="/dev/ttyUSB0")
        assert len(result) > 100

    @pytest.mark.parametrize("slug", [b.slug for b in list_boards()])
    def test_contains_fqbn(self, slug):
        board = get_board(slug)
        result = render_template(board, port="/dev/ttyUSB0")
        assert board.fqbn in result

    @pytest.mark.parametrize("slug", [b.slug for b in list_boards()])
    def test_has_validation_section(self, slug):
        board = get_board(slug)
        result = render_template(board, port="/dev/ttyUSB0")
        assert "Validation" in result
        assert "serial.Serial" in result

    @pytest.mark.parametrize("slug", [b.slug for b in list_boards()])
    def test_has_development_loop(self, slug):
        board = get_board(slug)
        result = render_template(board, port="/dev/ttyUSB0")
        assert "Development Loop" in result

    @pytest.mark.parametrize("slug", [b.slug for b in list_boards()])
    def test_no_unfilled_placeholders(self, slug):
        board = get_board(slug)
        result = render_template(board, port="/dev/ttyUSB0")
        placeholders = re.findall(r"\{[a-z_]+\}", result)
        assert placeholders == [], f"Unfilled placeholders in {slug}: {placeholders}"


class TestGenericRender:
    def test_renders_with_toolchain_data(self):
        from edesto_dev.templates import render_generic_template
        result = render_generic_template(
            board_name="Test Board",
            toolchain_name="test-tool",
            port="/dev/ttyUSB0",
            baud_rate=115200,
            compile_command="make build",
            upload_command="make flash PORT=/dev/ttyUSB0",
            monitor_command="make monitor",
            boot_delay=3,
            board_info={},
        )
        assert "Test Board" in result
        assert "make build" in result
        assert "make flash" in result
        assert "/dev/ttyUSB0" in result
        assert "115200" in result
        assert "Development Loop" in result
        assert "[READY]" in result

    def test_no_unfilled_placeholders(self):
        from edesto_dev.templates import render_generic_template
        result = render_generic_template(
            board_name="Board",
            toolchain_name="tool",
            port="/dev/ttyUSB0",
            baud_rate=115200,
            compile_command="compile",
            upload_command="upload",
            monitor_command=None,
            boot_delay=3,
            board_info={},
        )
        placeholders = re.findall(r"\{[a-z_]+\}", result)
        assert placeholders == []

    def test_monitor_command_omitted_when_none(self):
        from edesto_dev.templates import render_generic_template
        result = render_generic_template(
            board_name="Board",
            toolchain_name="tool",
            port="/dev/ttyUSB0",
            baud_rate=115200,
            compile_command="compile",
            upload_command="upload",
            monitor_command=None,
            boot_delay=3,
            board_info={},
        )
        assert "Monitor" not in result or "None" not in result

    def test_board_info_with_pitfalls(self):
        from edesto_dev.templates import render_generic_template
        result = render_generic_template(
            board_name="Board",
            toolchain_name="tool",
            port="/dev/ttyUSB0",
            baud_rate=115200,
            compile_command="compile",
            upload_command="upload",
            monitor_command=None,
            boot_delay=3,
            board_info={"pitfalls": ["Watch out for X"]},
        )
        assert "Watch out for X" in result


class TestRenderFromToolchain:
    def test_renders_from_arduino_toolchain(self):
        from edesto_dev.templates import render_from_toolchain
        from edesto_dev.toolchains.arduino import ArduinoToolchain
        tc = ArduinoToolchain()
        board = tc.get_board("esp32")
        result = render_from_toolchain(tc, board, "/dev/ttyUSB0")
        assert "ESP32" in result
        assert "arduino-cli compile" in result
        assert "/dev/ttyUSB0" in result
        assert "Development Loop" in result
        assert "[READY]" in result
