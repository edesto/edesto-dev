"""Tests for the edesto CLI."""

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from edesto_dev.cli import main
from edesto_dev.toolchain import Board, DetectedBoard, JtagConfig
from edesto_dev.toolchains import get_toolchain


def _get_board(slug):
    """Helper to look up a board from the Arduino toolchain."""
    tc = get_toolchain("arduino")
    return tc.get_board(slug)


@pytest.fixture
def runner():
    return CliRunner()


class TestInit:
    def test_init_with_board_and_port(self, runner):
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init", "--board", "esp32", "--port", "/dev/ttyUSB0"])
            assert result.exit_code == 0
            assert Path("SKILLS.md").exists()

    def test_init_generates_valid_content(self, runner):
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init", "--board", "esp32", "--port", "/dev/ttyUSB0"])
            content = Path("SKILLS.md").read_text()
            assert "esp32:esp32:esp32" in content
            assert "/dev/ttyUSB0" in content
            assert "Development Loop" in content

    def test_init_creates_all_copies(self, runner):
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init", "--board", "esp32", "--port", "/dev/ttyUSB0"])
            skills = Path("SKILLS.md").read_text()
            assert Path("CLAUDE.md").exists()
            assert Path(".cursorrules").exists()
            assert Path("AGENTS.md").exists()
            assert Path("CLAUDE.md").read_text() == skills
            assert Path(".cursorrules").read_text() == skills
            assert Path("AGENTS.md").read_text() == skills

    def test_init_unknown_board_fails(self, runner):
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init", "--board", "nonexistent", "--port", "/dev/ttyUSB0"])
            assert result.exit_code != 0
            assert "Unknown board" in result.output

    def test_init_asks_before_overwrite(self, runner):
        with runner.isolated_filesystem():
            Path("SKILLS.md").write_text("existing content")
            result = runner.invoke(main, ["init", "--board", "esp32", "--port", "/dev/ttyUSB0"], input="n\n")
            assert result.exit_code == 0
            assert Path("SKILLS.md").read_text() == "existing content"

    def test_init_overwrites_when_confirmed(self, runner):
        with runner.isolated_filesystem():
            Path("SKILLS.md").write_text("existing content")
            result = runner.invoke(main, ["init", "--board", "esp32", "--port", "/dev/ttyUSB0"], input="y\n")
            assert result.exit_code == 0
            assert "esp32:esp32:esp32" in Path("SKILLS.md").read_text()

    def test_init_all_boards_work(self, runner):
        from edesto_dev.toolchains import list_toolchains
        for tc in list_toolchains():
            for board in tc.list_boards():
                with runner.isolated_filesystem():
                    result = runner.invoke(main, ["init", "--board", board.slug, "--port", "/dev/ttyUSB0"])
                    assert result.exit_code == 0, f"Failed for {board.slug}: {result.output}"
                    assert Path("SKILLS.md").exists()


class TestInitAutoDetect:
    @patch("edesto_dev.cli.detect_all_boards")
    def test_auto_detects_single_board(self, mock_detect, runner):
        mock_detect.return_value = [DetectedBoard(board=_get_board("esp32"), port="/dev/cu.usbserial-0001", toolchain_name="arduino")]
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init"])
            assert result.exit_code == 0
            assert Path("SKILLS.md").exists()
            content = Path("SKILLS.md").read_text()
            assert "esp32:esp32:esp32" in content
            assert "/dev/cu.usbserial-0001" in content

    @patch("edesto_dev.cli.detect_all_boards")
    def test_auto_detect_prints_what_it_found(self, mock_detect, runner):
        mock_detect.return_value = [DetectedBoard(board=_get_board("esp32"), port="/dev/cu.usbserial-0001", toolchain_name="arduino")]
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init"])
            assert "Detected" in result.output or "detected" in result.output
            assert "ESP32" in result.output

    @patch("edesto_dev.cli.detect_all_boards")
    def test_auto_detect_multiple_boards_asks_user(self, mock_detect, runner):
        mock_detect.return_value = [
            DetectedBoard(board=_get_board("esp32"), port="/dev/cu.usbserial-0001", toolchain_name="arduino"),
            DetectedBoard(board=_get_board("arduino-uno"), port="/dev/ttyACM0", toolchain_name="arduino"),
        ]
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init"], input="1\n")
            assert result.exit_code == 0
            assert Path("SKILLS.md").exists()

    @patch("edesto_dev.cli.detect_all_boards", return_value=[])
    @patch("edesto_dev.cli.detect_toolchain", return_value=get_toolchain("arduino"))
    def test_auto_detect_no_boards_shows_error(self, mock_detect_tc, mock_detect, runner):
        """When a toolchain IS detected but no boards on USB, show an error."""
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init"])
            assert result.exit_code != 0
            assert "No boards detected" in result.output or "no boards" in result.output.lower()

    @patch("edesto_dev.cli.detect_all_boards")
    def test_board_flag_skips_detection(self, mock_detect, runner):
        """When --board and --port are provided, don't call detect_all_boards."""
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init", "--board", "esp32", "--port", "/dev/ttyUSB0"])
            assert result.exit_code == 0
            mock_detect.assert_not_called()

    @patch("edesto_dev.cli.detect_all_boards")
    def test_board_flag_without_port_detects_port(self, mock_detect, runner):
        # When --board is given without --port, the CLI calls toolchain.detect_boards()
        # (not detect_all_boards), so we need to mock the toolchain's detect_boards method
        board = _get_board("esp32")
        tc = get_toolchain("arduino")
        with patch.object(tc, "detect_boards") as mock_tc_detect:
            mock_tc_detect.return_value = [DetectedBoard(board=board, port="/dev/cu.usbserial-0001", toolchain_name="arduino")]
            with runner.isolated_filesystem():
                result = runner.invoke(main, ["init", "--board", "esp32"])
                assert result.exit_code == 0
                content = Path("SKILLS.md").read_text()
                assert "/dev/cu.usbserial-0001" in content


class TestInitWithToolchain:
    def test_toolchain_flag(self, runner):
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init", "--board", "esp32", "--port", "/dev/ttyUSB0", "--toolchain", "arduino"])
            assert result.exit_code == 0
            assert Path("SKILLS.md").exists()

    def test_unknown_toolchain(self, runner):
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init", "--board", "esp32", "--port", "/dev/ttyUSB0", "--toolchain", "nonexistent"])
            assert result.exit_code != 0
            assert "Unknown toolchain" in result.output


class TestBoards:
    def test_boards_lists_all(self, runner):
        result = runner.invoke(main, ["boards"])
        assert result.exit_code == 0
        assert "esp32" in result.output
        assert "arduino-uno" in result.output
        assert "rp2040" in result.output

    def test_boards_shows_board_names(self, runner):
        result = runner.invoke(main, ["boards"])
        assert "ESP32" in result.output

    def test_boards_shows_all_board_count(self, runner):
        from edesto_dev.toolchains import list_toolchains
        result = runner.invoke(main, ["boards"])
        for tc in list_toolchains():
            for board in tc.list_boards():
                assert board.slug in result.output, f"Missing {board.slug} in output"


class TestDoctor:
    def test_doctor_runs(self, runner):
        result = runner.invoke(main, ["doctor"])
        assert result.exit_code == 0

    def test_doctor_checks_toolchains(self, runner):
        result = runner.invoke(main, ["doctor"])
        assert "arduino" in result.output

    @patch("edesto_dev.toolchains.arduino.shutil.which", return_value=None)
    def test_doctor_warns_missing_arduino_cli(self, mock_which, runner):
        result = runner.invoke(main, ["doctor"])
        assert "not found" in result.output.lower() or "not installed" in result.output.lower()


class TestInitCustomFallback:
    @patch("edesto_dev.cli.detect_debug_tools", return_value=[])
    @patch("edesto_dev.cli.detect_all_boards", return_value=[])
    @patch("edesto_dev.cli.detect_toolchain", return_value=None)
    def test_custom_fallback_prompts_user(self, mock_detect_tc, mock_detect_boards, mock_debug, runner):
        with runner.isolated_filesystem():
            # Simulate user input: compile, upload, baud, port, board name
            user_input = "make build\nmake flash\n115200\n/dev/ttyUSB0\nMy Board\n"
            result = runner.invoke(main, ["init"], input=user_input)
            assert result.exit_code == 0
            assert Path("SKILLS.md").exists()
            assert Path("edesto.toml").exists()

            # Verify SKILLS.md content
            content = Path("SKILLS.md").read_text()
            assert "make build" in content
            assert "make flash" in content
            assert "My Board" in content

            # Verify edesto.toml content
            toml_content = Path("edesto.toml").read_text()
            assert "make build" in toml_content
            assert "make flash" in toml_content

    @patch("edesto_dev.cli.detect_debug_tools", return_value=[])
    @patch("edesto_dev.cli.detect_all_boards", return_value=[])
    @patch("edesto_dev.cli.detect_toolchain", return_value=None)
    def test_custom_fallback_saves_edesto_toml(self, mock_detect_tc, mock_detect_boards, mock_debug, runner):
        with runner.isolated_filesystem():
            user_input = "gcc -o firmware main.c\nopenocd -f upload.cfg\n9600\n/dev/ttyACM0\nSTM32\n"
            result = runner.invoke(main, ["init"], input=user_input)
            assert result.exit_code == 0
            assert "edesto.toml" in result.output
            toml = Path("edesto.toml").read_text()
            assert "9600" in toml


class TestIntegration:
    def test_full_workflow(self, runner):
        """Test the full init -> read -> verify workflow."""
        with runner.isolated_filesystem():
            # Generate SKILLS.md
            result = runner.invoke(main, ["init", "--board", "esp32", "--port", "/dev/cu.usbserial-0001"])
            assert result.exit_code == 0

            # Verify SKILLS.md content
            content = Path("SKILLS.md").read_text()
            assert "# Embedded Development: ESP32" in content
            assert "esp32:esp32:esp32" in content
            assert "/dev/cu.usbserial-0001" in content
            assert "arduino-cli compile" in content
            assert "arduino-cli upload" in content
            assert "Development Loop" in content
            assert "serial.Serial" in content
            assert "[READY]" in content
            assert "ADC2" in content  # ESP32-specific pitfall

            # Verify all copies match
            assert Path("CLAUDE.md").read_text() == content
            assert Path(".cursorrules").read_text() == content
            assert Path("AGENTS.md").read_text() == content

    def test_help_output(self, runner):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "init" in result.output
        assert "doctor" in result.output
        assert "boards" in result.output


class TestIntegrationMultiToolchain:
    """End-to-end integration tests verifying the complete flow for different toolchains."""

    def test_arduino_project_flow(self, runner):
        """Arduino project: .ino file -> edesto init -> SKILLS.md with arduino-cli commands."""
        with runner.isolated_filesystem():
            Path("sketch.ino").write_text("void setup() { Serial.begin(115200); }")
            result = runner.invoke(main, ["init", "--board", "esp32", "--port", "/dev/ttyUSB0"])
            assert result.exit_code == 0
            content = Path("SKILLS.md").read_text()
            assert "arduino-cli compile" in content
            assert "arduino-cli upload" in content
            assert "/dev/ttyUSB0" in content
            assert "ESP32" in content

    @patch("edesto_dev.cli.detect_all_boards")
    def test_platformio_project_flow(self, mock_detect_boards, runner):
        """PlatformIO project: platformio.ini detected -> CLAUDE.md with pio commands."""
        # PlatformIO has no board definitions, so we mock auto-detection
        # to return a board (as if USB detection found one).
        esp32_board = _get_board("esp32")
        mock_detect_boards.return_value = [
            DetectedBoard(board=esp32_board, port="/dev/ttyUSB0", toolchain_name="platformio"),
        ]
        with runner.isolated_filesystem():
            # Create platformio.ini so detect_toolchain picks up PlatformIO
            Path("platformio.ini").write_text("[env:esp32dev]\nboard = esp32dev\n")
            result = runner.invoke(main, ["init"])
            assert result.exit_code == 0
            content = Path("SKILLS.md").read_text()
            assert "pio run" in content
            assert "/dev/ttyUSB0" in content
            # Should NOT contain arduino-cli commands
            assert "arduino-cli" not in content

    @patch("edesto_dev.cli.detect_all_boards")
    def test_espidf_project_flow(self, mock_detect_boards, runner):
        """ESP-IDF project: CMakeLists.txt + sdkconfig -> CLAUDE.md with idf.py commands."""
        esp32_board = _get_board("esp32")
        mock_detect_boards.return_value = [
            DetectedBoard(board=esp32_board, port="/dev/ttyUSB0", toolchain_name="espidf"),
        ]
        with runner.isolated_filesystem():
            Path("CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.16)")
            Path("sdkconfig").write_text("")
            result = runner.invoke(main, ["init"])
            assert result.exit_code == 0
            content = Path("SKILLS.md").read_text()
            assert "idf.py build" in content
            assert "idf.py" in content
            assert "/dev/ttyUSB0" in content
            # Should NOT contain arduino-cli commands
            assert "arduino-cli" not in content

    @patch("edesto_dev.cli.detect_all_boards")
    def test_micropython_project_flow(self, mock_detect_boards, runner):
        """MicroPython project: main.py -> CLAUDE.md with mpremote commands."""
        esp32_board = _get_board("esp32")
        mock_detect_boards.return_value = [
            DetectedBoard(board=esp32_board, port="/dev/ttyUSB0", toolchain_name="micropython"),
        ]
        with runner.isolated_filesystem():
            Path("main.py").write_text("import machine\nprint('hello')")
            result = runner.invoke(main, ["init"])
            assert result.exit_code == 0
            content = Path("SKILLS.md").read_text()
            assert "mpremote" in content
            assert "/dev/ttyUSB0" in content
            # Should NOT contain arduino-cli commands
            assert "arduino-cli" not in content

    @patch("edesto_dev.cli.detect_debug_tools", return_value=[])
    @patch("edesto_dev.cli.detect_all_boards", return_value=[])
    @patch("edesto_dev.cli.detect_toolchain", return_value=None)
    def test_custom_project_flow(self, mock_detect_tc, mock_detect_boards, mock_debug, runner):
        """Custom project: manual fallback -> CLAUDE.md with user-specified commands."""
        with runner.isolated_filesystem():
            user_input = "make build\nmake flash PORT={port}\n9600\n/dev/ttyACM0\nMy Custom Board\n"
            result = runner.invoke(main, ["init"], input=user_input)
            assert result.exit_code == 0
            content = Path("SKILLS.md").read_text()
            assert "make build" in content
            assert "make flash" in content
            assert "/dev/ttyACM0" in content
            assert "My Custom Board" in content
            # Should NOT contain any toolchain-specific commands
            assert "arduino-cli" not in content
            assert "pio run" not in content
            assert "idf.py" not in content

    def test_edesto_toml_overrides_ino_detection(self, runner):
        """edesto.toml takes priority over .ino file detection."""
        with runner.isolated_filesystem():
            # Create both an .ino file and edesto.toml
            Path("sketch.ino").write_text("void setup() {}")
            Path("edesto.toml").write_text(
                '[toolchain]\n'
                'compile = "make build"\n'
                'upload = "make flash PORT={port}"\n'
                '\n'
                '[serial]\n'
                'baud_rate = 115200\n'
            )
            # Custom toolchain is detected from edesto.toml (has no boards).
            # No --board/--port -> enters auto-detect path.
            # detect_all_boards() returns [] (no USB boards) and toolchain IS set
            # (custom from edesto.toml), so it errors: "No boards detected."
            # We need to mock detect_all_boards to return a board.
            esp32_board = Board(slug="custom", name="Custom Board", baud_rate=115200)
            with patch("edesto_dev.cli.detect_all_boards") as mock_detect:
                mock_detect.return_value = [
                    DetectedBoard(board=esp32_board, port="/dev/ttyUSB0", toolchain_name="custom"),
                ]
                result = runner.invoke(main, ["init"])
                assert result.exit_code == 0
                content = Path("SKILLS.md").read_text()
                # Custom commands from edesto.toml, not arduino-cli
                assert "make build" in content
                assert "arduino-cli" not in content

    def test_platformio_toolchain_flag_with_board_fails(self, runner):
        """Using --toolchain platformio --board esp32 fails because PlatformIO has no board defs."""
        with runner.isolated_filesystem():
            result = runner.invoke(
                main,
                ["init", "--board", "esp32", "--port", "/dev/ttyUSB0", "--toolchain", "platformio"],
            )
            assert result.exit_code != 0
            assert "Unknown board" in result.output

    def test_boards_lists_arduino_toolchain(self, runner):
        """edesto boards lists boards from all registered toolchains (only Arduino has boards)."""
        result = runner.invoke(main, ["boards"])
        assert result.exit_code == 0
        # Arduino boards should be listed
        assert "arduino" in result.output.lower()
        assert "esp32" in result.output

    def test_boards_toolchain_filter(self, runner):
        """edesto boards --toolchain arduino only shows Arduino boards."""
        result = runner.invoke(main, ["boards", "--toolchain", "arduino"])
        assert result.exit_code == 0
        assert "esp32" in result.output
        assert "arduino-uno" in result.output

    def test_boards_toolchain_filter_empty(self, runner):
        """edesto boards --toolchain platformio shows no boards (PlatformIO has no board defs)."""
        result = runner.invoke(main, ["boards", "--toolchain", "platformio"])
        assert result.exit_code == 0
        assert "0" in result.output  # "Supported boards (0):"

    def test_doctor_checks_all_toolchains(self, runner):
        """edesto doctor checks all registered toolchains."""
        result = runner.invoke(main, ["doctor"])
        assert result.exit_code == 0
        assert "arduino" in result.output
        assert "platformio" in result.output
        assert "espidf" in result.output
        assert "micropython" in result.output


class TestDoctorDebugTools:
    @patch("edesto_dev.cli.detect_debug_tools", return_value=["saleae", "openocd", "scope"])
    def test_doctor_shows_debug_tools(self, mock_debug, runner):
        result = runner.invoke(main, ["doctor"])
        assert "saleae" in result.output.lower()
        assert "openocd" in result.output.lower()
        assert "scope" in result.output.lower() or "oscilloscope" in result.output.lower()

    @patch("edesto_dev.cli.detect_debug_tools", return_value=[])
    def test_doctor_shows_no_debug_tools(self, mock_debug, runner):
        result = runner.invoke(main, ["doctor"])
        assert result.exit_code == 0


class TestInitDebugTools:
    @patch("edesto_dev.cli.detect_debug_tools", return_value=["saleae", "openocd"])
    def test_init_includes_detected_debug_tools(self, mock_debug, runner):
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init", "--board", "esp32", "--port", "/dev/ttyUSB0"])
            assert result.exit_code == 0
            content = Path("SKILLS.md").read_text()
            assert "### Logic Analyzer" in content
            assert "### JTAG/SWD" in content
            assert "### Oscilloscope" not in content

    @patch("edesto_dev.cli.detect_debug_tools", return_value=[])
    def test_init_no_debug_tools(self, mock_debug, runner):
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init", "--board", "esp32", "--port", "/dev/ttyUSB0"])
            assert result.exit_code == 0
            content = Path("SKILLS.md").read_text()
            assert "### Serial Output" in content
            assert "### Logic Analyzer" not in content
            assert "### JTAG/SWD" not in content
            assert "### Oscilloscope" not in content


class TestInitJtag:
    @patch("edesto_dev.cli.detect_debug_tools", return_value=["openocd"])
    def test_upload_jtag_flag_prompts_for_setup(self, mock_debug, runner):
        """--upload jtag triggers JTAG setup flow."""
        with runner.isolated_filesystem():
            # Input: probe choice (1=ST-Link), target (accept default stm32f4x), serial? (n)
            user_input = "1\n\nn\n"
            result = runner.invoke(main, ["init", "--board", "stm32-nucleo", "--upload", "jtag"], input=user_input)
            assert result.exit_code == 0
            assert Path("SKILLS.md").exists()
            content = Path("SKILLS.md").read_text()
            assert "JTAG" in content or "openocd" in content.lower()
            assert "stlink" in content.lower() or "stm32f4x" in content

    @patch("edesto_dev.cli.detect_debug_tools", return_value=["openocd"])
    def test_upload_jtag_with_serial_port(self, mock_debug, runner):
        """JTAG setup with serial port includes serial section."""
        with runner.isolated_filesystem():
            # Input: probe (1=ST-Link), target (accept default), serial? (y), port, baud
            user_input = "1\n\ny\n/dev/cu.usbmodem1103\n115200\n"
            result = runner.invoke(main, ["init", "--board", "stm32-nucleo", "--upload", "jtag"], input=user_input)
            assert result.exit_code == 0
            content = Path("SKILLS.md").read_text()
            assert "### Serial Output" in content
            assert "/dev/cu.usbmodem1103" in content

    @patch("edesto_dev.cli.detect_debug_tools", return_value=["openocd"])
    def test_upload_jtag_without_serial_port(self, mock_debug, runner):
        """JTAG setup without serial port omits serial section."""
        with runner.isolated_filesystem():
            # Input: probe (1=ST-Link), target (accept default), serial? (n)
            user_input = "1\n\nn\n"
            result = runner.invoke(main, ["init", "--board", "stm32-nucleo", "--upload", "jtag"], input=user_input)
            assert result.exit_code == 0
            content = Path("SKILLS.md").read_text()
            assert "### Serial Output" not in content

    @patch("edesto_dev.cli.detect_debug_tools", return_value=[])
    def test_upload_jtag_without_openocd_fails(self, mock_debug, runner):
        """--upload jtag fails if OpenOCD is not installed."""
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init", "--board", "stm32-nucleo", "--upload", "jtag"])
            assert result.exit_code != 0
            assert "openocd" in result.output.lower()

    @patch("edesto_dev.cli.detect_debug_tools", return_value=["openocd"])
    def test_upload_jtag_saves_edesto_toml(self, mock_debug, runner):
        """JTAG config is saved to edesto.toml."""
        with runner.isolated_filesystem():
            user_input = "1\n\nn\n"
            result = runner.invoke(main, ["init", "--board", "stm32-nucleo", "--upload", "jtag"], input=user_input)
            assert result.exit_code == 0
            assert Path("edesto.toml").exists()
            toml_content = Path("edesto.toml").read_text()
            assert "[jtag]" in toml_content
            assert "stlink" in toml_content

    @patch("edesto_dev.cli.detect_all_boards", return_value=[])
    @patch("edesto_dev.cli.detect_toolchain", return_value=None)
    @patch("edesto_dev.cli.detect_debug_tools", return_value=["openocd"])
    def test_auto_fallback_offers_jtag(self, mock_debug, mock_detect_tc, mock_detect_boards, runner):
        """When no USB boards found and OpenOCD installed, offer JTAG setup."""
        with runner.isolated_filesystem():
            # Input: yes to JTAG, board slug, probe (1=ST-Link), target (accept default), serial? (n)
            user_input = "y\nstm32-nucleo\n1\n\nn\n"
            result = runner.invoke(main, ["init"], input=user_input)
            assert result.exit_code == 0
            assert Path("SKILLS.md").exists()
            content = Path("SKILLS.md").read_text()
            assert "JTAG" in content or "openocd" in content.lower()

    @patch("edesto_dev.cli.detect_all_boards", return_value=[])
    @patch("edesto_dev.cli.detect_toolchain", return_value=None)
    @patch("edesto_dev.cli.detect_debug_tools", return_value=["openocd"])
    def test_auto_fallback_jtag_declined_goes_to_custom(self, mock_debug, mock_detect_tc, mock_detect_boards, runner):
        """Declining JTAG falls through to custom manual setup."""
        with runner.isolated_filesystem():
            # Input: no to JTAG, then custom setup: compile, upload, baud, port, name
            user_input = "n\nmake build\nmake flash\n115200\n/dev/ttyUSB0\nMy Board\n"
            result = runner.invoke(main, ["init"], input=user_input)
            assert result.exit_code == 0
            content = Path("SKILLS.md").read_text()
            assert "make build" in content

    def test_upload_serial_is_default(self, runner):
        """--upload serial (or no --upload) uses the normal USB path."""
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init", "--board", "esp32", "--port", "/dev/ttyUSB0"])
            assert result.exit_code == 0
            content = Path("SKILLS.md").read_text()
            assert "connected via USB" in content


class TestInitJtagIntegration:
    @patch("edesto_dev.cli.detect_debug_tools", return_value=["openocd"])
    def test_full_jtag_workflow(self, mock_debug, runner):
        """Full JTAG init -> verify SKILLS.md + edesto.toml + copies."""
        with runner.isolated_filesystem():
            # Input: probe (1=ST-Link), target (accept default stm32f4x), serial? (n)
            user_input = "1\n\nn\n"
            result = runner.invoke(main, ["init", "--board", "stm32-nucleo", "--upload", "jtag"], input=user_input)
            assert result.exit_code == 0

            # Verify SKILLS.md content
            content = Path("SKILLS.md").read_text()
            assert "STM32 Nucleo-64" in content
            assert "JTAG" in content
            assert "stlink" in content.lower()
            assert "stm32f4x" in content
            assert "openocd" in content.lower()
            assert "### JTAG/SWD" in content
            assert "connected via USB" not in content
            # Should have compile command from Arduino toolchain
            assert "arduino-cli compile" in content
            # Should have OpenOCD upload command
            assert "program build/firmware.elf verify reset exit" in content
            # Should NOT have serial section (user said no)
            assert "### Serial Output" not in content

            # Verify copies match
            assert Path("CLAUDE.md").read_text() == content
            assert Path(".cursorrules").read_text() == content
            assert Path("AGENTS.md").read_text() == content

            # Verify edesto.toml
            assert Path("edesto.toml").exists()
            toml = Path("edesto.toml").read_text()
            assert "[jtag]" in toml
            assert 'interface = "stlink"' in toml
            assert 'target = "stm32f4x"' in toml
            # No [serial] section since user declined
            assert "[serial]" not in toml

    @patch("edesto_dev.cli.detect_debug_tools", return_value=["openocd"])
    def test_full_jtag_workflow_with_serial(self, mock_debug, runner):
        """Full JTAG init with serial port -> verify serial section present."""
        with runner.isolated_filesystem():
            # Input: probe (1=ST-Link), target (accept default), serial? (y), port, baud
            user_input = "1\n\ny\n/dev/cu.usbmodem1103\n115200\n"
            result = runner.invoke(main, ["init", "--board", "stm32-nucleo", "--upload", "jtag"], input=user_input)
            assert result.exit_code == 0

            content = Path("SKILLS.md").read_text()
            assert "JTAG" in content
            assert "### Serial Output" in content
            assert "/dev/cu.usbmodem1103" in content
            assert "115200" in content

            # Verify edesto.toml has both sections
            toml = Path("edesto.toml").read_text()
            assert "[jtag]" in toml
            assert "[serial]" in toml
            assert "/dev/cu.usbmodem1103" in toml

    @patch("edesto_dev.cli.detect_debug_tools", return_value=["openocd"])
    def test_upload_jtag_requires_board(self, mock_debug, runner):
        """--upload jtag without --board fails with helpful error."""
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init", "--upload", "jtag"])
            assert result.exit_code != 0
            assert "board" in result.output.lower()
