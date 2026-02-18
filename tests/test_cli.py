"""Tests for the edesto CLI."""

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from edesto_dev.cli import main
from edesto_dev.toolchain import DetectedBoard
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
            assert Path("CLAUDE.md").exists()

    def test_init_generates_valid_content(self, runner):
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init", "--board", "esp32", "--port", "/dev/ttyUSB0"])
            content = Path("CLAUDE.md").read_text()
            assert "esp32:esp32:esp32" in content
            assert "/dev/ttyUSB0" in content
            assert "Development Loop" in content

    def test_init_also_creates_cursorrules(self, runner):
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init", "--board", "esp32", "--port", "/dev/ttyUSB0"])
            assert Path(".cursorrules").exists()
            claude = Path("CLAUDE.md").read_text()
            cursor = Path(".cursorrules").read_text()
            assert claude == cursor

    def test_init_unknown_board_fails(self, runner):
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init", "--board", "nonexistent", "--port", "/dev/ttyUSB0"])
            assert result.exit_code != 0
            assert "Unknown board" in result.output

    def test_init_asks_before_overwrite(self, runner):
        with runner.isolated_filesystem():
            Path("CLAUDE.md").write_text("existing content")
            result = runner.invoke(main, ["init", "--board", "esp32", "--port", "/dev/ttyUSB0"], input="n\n")
            assert result.exit_code == 0
            assert Path("CLAUDE.md").read_text() == "existing content"

    def test_init_overwrites_when_confirmed(self, runner):
        with runner.isolated_filesystem():
            Path("CLAUDE.md").write_text("existing content")
            result = runner.invoke(main, ["init", "--board", "esp32", "--port", "/dev/ttyUSB0"], input="y\n")
            assert result.exit_code == 0
            assert "esp32:esp32:esp32" in Path("CLAUDE.md").read_text()

    def test_init_all_boards_work(self, runner):
        from edesto_dev.toolchains import list_toolchains
        for tc in list_toolchains():
            for board in tc.list_boards():
                with runner.isolated_filesystem():
                    result = runner.invoke(main, ["init", "--board", board.slug, "--port", "/dev/ttyUSB0"])
                    assert result.exit_code == 0, f"Failed for {board.slug}: {result.output}"
                    assert Path("CLAUDE.md").exists()


class TestInitAutoDetect:
    @patch("edesto_dev.cli.detect_all_boards")
    def test_auto_detects_single_board(self, mock_detect, runner):
        mock_detect.return_value = [DetectedBoard(board=_get_board("esp32"), port="/dev/cu.usbserial-0001", toolchain_name="arduino")]
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init"])
            assert result.exit_code == 0
            assert Path("CLAUDE.md").exists()
            content = Path("CLAUDE.md").read_text()
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
            assert Path("CLAUDE.md").exists()

    @patch("edesto_dev.cli.detect_all_boards")
    def test_auto_detect_no_boards_shows_error(self, mock_detect, runner):
        mock_detect.return_value = []
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
                content = Path("CLAUDE.md").read_text()
                assert "/dev/cu.usbserial-0001" in content


class TestInitWithToolchain:
    def test_toolchain_flag(self, runner):
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init", "--board", "esp32", "--port", "/dev/ttyUSB0", "--toolchain", "arduino"])
            assert result.exit_code == 0
            assert Path("CLAUDE.md").exists()

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


class TestIntegration:
    def test_full_workflow(self, runner):
        """Test the full init -> read -> verify workflow."""
        with runner.isolated_filesystem():
            # Generate CLAUDE.md
            result = runner.invoke(main, ["init", "--board", "esp32", "--port", "/dev/cu.usbserial-0001"])
            assert result.exit_code == 0

            # Verify CLAUDE.md content
            content = Path("CLAUDE.md").read_text()
            assert "# Embedded Development: ESP32" in content
            assert "esp32:esp32:esp32" in content
            assert "/dev/cu.usbserial-0001" in content
            assert "arduino-cli compile" in content
            assert "arduino-cli upload" in content
            assert "Development Loop" in content
            assert "serial.Serial" in content
            assert "[READY]" in content
            assert "ADC2" in content  # ESP32-specific pitfall

            # Verify .cursorrules matches
            assert Path(".cursorrules").read_text() == content

    def test_help_output(self, runner):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "init" in result.output
        assert "doctor" in result.output
        assert "boards" in result.output
