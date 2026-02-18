"""Tests for SKILLS.md template rendering."""

import re

import pytest
from edesto_dev.toolchains.arduino import ArduinoToolchain
from edesto_dev.templates import render_template

_arduino = ArduinoToolchain()


def get_board(slug):
    """Helper: look up a board via the Arduino toolchain."""
    board = _arduino.get_board(slug)
    if board is None:
        raise KeyError(f"Unknown board: {slug}")
    return board


def list_boards():
    """Helper: list all boards via the Arduino toolchain."""
    return _arduino.list_boards()


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
        assert "### Serial Output" in result
        assert "serial.Serial" in result
        assert "[READY]" in result
        assert "115200" in result

    def test_has_serial_conventions(self):
        board = get_board("esp32")
        result = render_template(board, port="/dev/ttyUSB0")
        assert "115200" in result
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

    def test_has_debugging_section(self):
        board = get_board("esp32")
        result = render_template(board, port="/dev/ttyUSB0")
        assert "## Debugging" in result
        assert "### Serial Output" in result


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
    def test_has_debugging_section(self, slug):
        board = get_board(slug)
        result = render_template(board, port="/dev/ttyUSB0")
        assert "## Debugging" in result
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

    def test_has_setup_section_for_arduino(self):
        from edesto_dev.templates import render_from_toolchain
        from edesto_dev.toolchains.arduino import ArduinoToolchain
        tc = ArduinoToolchain()
        board = tc.get_board("esp32")
        result = render_from_toolchain(tc, board, "/dev/ttyUSB0")
        assert "## Setup" in result
        assert "arduino-cli core install" in result

    def test_has_troubleshooting_section(self):
        from edesto_dev.templates import render_from_toolchain
        from edesto_dev.toolchains.arduino import ArduinoToolchain
        tc = ArduinoToolchain()
        board = tc.get_board("esp32")
        result = render_from_toolchain(tc, board, "/dev/ttyUSB0")
        assert "## Troubleshooting" in result
        assert "baud rate" in result.lower()
        assert "Permission denied" in result

    def test_validation_has_error_handling(self):
        from edesto_dev.templates import render_from_toolchain
        from edesto_dev.toolchains.arduino import ArduinoToolchain
        tc = ArduinoToolchain()
        board = tc.get_board("esp32")
        result = render_from_toolchain(tc, board, "/dev/ttyUSB0")
        assert "SerialException" in result
        assert "[DONE]" in result

    def test_capabilities_merged_with_includes(self):
        from edesto_dev.templates import render_from_toolchain
        from edesto_dev.toolchains.arduino import ArduinoToolchain
        tc = ArduinoToolchain()
        board = tc.get_board("esp32")
        result = render_from_toolchain(tc, board, "/dev/ttyUSB0")
        # WiFi capability should appear with its include on the same line
        lines = result.split("\n")
        wifi_lines = [l for l in lines if "Wifi" in l and "#include" in l]
        assert wifi_lines, "WiFi capability should include #include directive"

    def test_no_setup_section_when_not_needed(self):
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
            setup_info=None,
        )
        assert "## Setup" not in result


class TestDebugToolSections:
    def test_saleae_section_when_detected(self):
        from edesto_dev.templates import render_generic_template
        result = render_generic_template(
            board_name="ESP32",
            toolchain_name="arduino",
            port="/dev/ttyUSB0",
            baud_rate=115200,
            compile_command="compile",
            upload_command="upload",
            monitor_command=None,
            boot_delay=3,
            board_info={},
            debug_tools=["saleae"],
        )
        assert "### Logic Analyzer" in result
        assert "Manager.connect" in result
        assert "export_data_table" in result

    def test_saleae_section_absent_when_not_detected(self):
        from edesto_dev.templates import render_generic_template
        result = render_generic_template(
            board_name="ESP32",
            toolchain_name="arduino",
            port="/dev/ttyUSB0",
            baud_rate=115200,
            compile_command="compile",
            upload_command="upload",
            monitor_command=None,
            boot_delay=3,
            board_info={},
            debug_tools=[],
        )
        assert "### Logic Analyzer" not in result

    def test_saleae_has_connection_check_guidance(self):
        from edesto_dev.templates import render_generic_template
        result = render_generic_template(
            board_name="ESP32",
            toolchain_name="arduino",
            port="/dev/ttyUSB0",
            baud_rate=115200,
            compile_command="compile",
            upload_command="upload",
            monitor_command=None,
            boot_delay=3,
            board_info={},
            debug_tools=["saleae"],
        )
        assert "ask the user to verify" in result.lower() or "verify" in result.lower()

    def test_openocd_section_when_detected(self):
        from edesto_dev.templates import render_generic_template
        result = render_generic_template(
            board_name="ESP32",
            toolchain_name="arduino",
            port="/dev/ttyUSB0",
            baud_rate=115200,
            compile_command="compile",
            upload_command="upload",
            monitor_command=None,
            boot_delay=3,
            board_info={},
            debug_tools=["openocd"],
        )
        assert "### JTAG/SWD" in result
        assert "OpenOCD" in result
        assert "CFSR" in result or "fault" in result.lower()

    def test_openocd_section_absent_when_not_detected(self):
        from edesto_dev.templates import render_generic_template
        result = render_generic_template(
            board_name="ESP32",
            toolchain_name="arduino",
            port="/dev/ttyUSB0",
            baud_rate=115200,
            compile_command="compile",
            upload_command="upload",
            monitor_command=None,
            boot_delay=3,
            board_info={},
            debug_tools=[],
        )
        assert "### JTAG/SWD" not in result

    def test_scope_section_when_detected(self):
        from edesto_dev.templates import render_generic_template
        result = render_generic_template(
            board_name="ESP32",
            toolchain_name="arduino",
            port="/dev/ttyUSB0",
            baud_rate=115200,
            compile_command="compile",
            upload_command="upload",
            monitor_command=None,
            boot_delay=3,
            board_info={},
            debug_tools=["scope"],
        )
        assert "### Oscilloscope" in result
        assert "pyvisa" in result
        assert "FREQuency" in result or "frequency" in result.lower()

    def test_scope_section_absent_when_not_detected(self):
        from edesto_dev.templates import render_generic_template
        result = render_generic_template(
            board_name="ESP32",
            toolchain_name="arduino",
            port="/dev/ttyUSB0",
            baud_rate=115200,
            compile_command="compile",
            upload_command="upload",
            monitor_command=None,
            boot_delay=3,
            board_info={},
            debug_tools=[],
        )
        assert "### Oscilloscope" not in result
