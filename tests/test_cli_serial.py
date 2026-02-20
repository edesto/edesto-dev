"""Tests for serial, debug, and config CLI commands."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from edesto_dev.cli import main
from edesto_dev.serial.port import PortInfo, SerialError
from edesto_dev.serial.reader import ReadResult, SendResult


@pytest.fixture
def runner():
    return CliRunner()


class TestSerialPorts:
    @patch("edesto_dev.cli.list_serial_ports")
    def test_lists_devices(self, mock_list, runner):
        mock_list.return_value = [
            PortInfo(device="/dev/ttyUSB0", description="CP2102", hwid="USB"),
            PortInfo(device="/dev/ttyACM0", description="Arduino", hwid="USB"),
        ]
        result = runner.invoke(main, ["serial", "ports"])
        assert result.exit_code == 0
        assert "/dev/ttyUSB0" in result.output
        assert "/dev/ttyACM0" in result.output

    @patch("edesto_dev.cli.list_serial_ports")
    def test_lists_devices_json(self, mock_list, runner):
        mock_list.return_value = [
            PortInfo(device="/dev/ttyUSB0", description="CP2102", hwid="USB"),
        ]
        result = runner.invoke(main, ["serial", "ports", "--json"])
        assert result.exit_code == 0
        import json
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["device"] == "/dev/ttyUSB0"


class TestSerialRead:
    @patch("edesto_dev.cli.serial_read")
    @patch("edesto_dev.cli.open_serial")
    @patch("edesto_dev.cli.resolve_port_and_baud")
    def test_basic_read(self, mock_resolve, mock_open, mock_read, runner):
        mock_resolve.return_value = ("/dev/ttyUSB0", 115200)
        mock_ser = MagicMock()
        mock_open.return_value = mock_ser
        mock_read.return_value = ReadResult(
            lines=["hello", "world"],
            parsed_lines=[],
            duration_seconds=2.0,
            exit_reason="duration",
        )
        with runner.isolated_filesystem():
            Path("edesto.toml").write_text('[serial]\nport = "/dev/ttyUSB0"\n')
            result = runner.invoke(main, ["serial", "read", "--port", "/dev/ttyUSB0"])
        assert result.exit_code == 0
        assert "hello" in result.output

    @patch("edesto_dev.cli.serial_read")
    @patch("edesto_dev.cli.open_serial")
    @patch("edesto_dev.cli.resolve_port_and_baud")
    def test_read_json(self, mock_resolve, mock_open, mock_read, runner):
        mock_resolve.return_value = ("/dev/ttyUSB0", 115200)
        mock_ser = MagicMock()
        mock_open.return_value = mock_ser
        mock_read.return_value = ReadResult(
            lines=["hello"],
            parsed_lines=[],
            duration_seconds=1.0,
            exit_reason="duration",
        )
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["serial", "read", "--port", "/dev/ttyUSB0", "--json"])
        assert result.exit_code == 0
        import json
        data = json.loads(result.output)
        assert "lines" in data

    @patch("edesto_dev.cli.open_serial")
    @patch("edesto_dev.cli.resolve_port_and_baud")
    def test_read_port_not_found(self, mock_resolve, mock_open, runner):
        mock_resolve.return_value = ("/dev/nonexistent", 115200)
        mock_open.side_effect = SerialError("Port not found", exit_code=2)
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["serial", "read", "--port", "/dev/nonexistent"])
        assert result.exit_code == 2


class TestSerialSend:
    @patch("edesto_dev.cli.serial_send")
    @patch("edesto_dev.cli.open_serial")
    @patch("edesto_dev.cli.resolve_port_and_baud")
    def test_basic_send(self, mock_resolve, mock_open, mock_send, runner):
        mock_resolve.return_value = ("/dev/ttyUSB0", 115200)
        mock_ser = MagicMock()
        mock_open.return_value = mock_ser
        mock_send.return_value = SendResult(
            lines=["[OK]"],
            parsed_lines=[],
            duration_seconds=0.5,
            exit_reason="success_marker",
            exit_code=0,
            was_error=False,
        )
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["serial", "send", "test_cmd", "--port", "/dev/ttyUSB0"])
        assert result.exit_code == 0
        assert "[OK]" in result.output

    @patch("edesto_dev.cli.serial_send")
    @patch("edesto_dev.cli.open_serial")
    @patch("edesto_dev.cli.resolve_port_and_baud")
    def test_send_quiet_timeout(self, mock_resolve, mock_open, mock_send, runner):
        mock_resolve.return_value = ("/dev/ttyUSB0", 115200)
        mock_ser = MagicMock()
        mock_open.return_value = mock_ser
        mock_send.return_value = SendResult(
            lines=["response"],
            parsed_lines=[],
            duration_seconds=0.5,
            exit_reason="quiet_timeout",
            exit_code=0,
            was_error=False,
        )
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["serial", "send", "cmd", "--port", "/dev/ttyUSB0"])
        assert result.exit_code == 0


class TestSerialMonitor:
    @patch("edesto_dev.cli.serial_monitor")
    @patch("edesto_dev.cli.open_serial")
    @patch("edesto_dev.cli.resolve_port_and_baud")
    def test_monitor_runs(self, mock_resolve, mock_open, mock_monitor, runner):
        mock_resolve.return_value = ("/dev/ttyUSB0", 115200)
        mock_ser = MagicMock()
        mock_open.return_value = mock_ser
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["serial", "monitor", "--port", "/dev/ttyUSB0", "--duration", "1"])
        assert result.exit_code == 0


class TestDebugScan:
    def test_scan_creates_cache(self, runner):
        with runner.isolated_filesystem():
            Path("main.ino").write_text('''
void setup() {
    Serial.begin(115200);
    Serial.println("[READY]");
}
void loop() {}
''')
            Path("edesto.toml").write_text('[serial]\nport = "/dev/ttyUSB0"\n')
            result = runner.invoke(main, ["debug", "scan"])
            assert result.exit_code == 0
            assert Path(".edesto/debug-scan.json").exists()

    def test_scan_json_output(self, runner):
        with runner.isolated_filesystem():
            Path("main.ino").write_text('void setup() { Serial.begin(115200); }')
            Path("edesto.toml").write_text('[serial]\nport = "/dev/ttyUSB0"\n')
            result = runner.invoke(main, ["debug", "scan", "--json"])
            assert result.exit_code == 0
            import json
            data = json.loads(result.output)
            assert "serial" in data
            assert "logging_api" in data


class TestDebugReset:
    def test_clears_state(self, runner):
        with runner.isolated_filesystem():
            Path(".edesto").mkdir()
            Path(".edesto/.gitignore").write_text("*\n")
            Path(".edesto/debug-log.jsonl").write_text('{"a":1}\n')
            Path(".edesto/debug-scan.json").write_text('{}')
            result = runner.invoke(main, ["debug", "reset"])
            assert result.exit_code == 0
            assert not Path(".edesto/debug-log.jsonl").exists()
            assert not Path(".edesto/debug-scan.json").exists()


class TestConfigCommand:
    def test_list_config(self, runner):
        with runner.isolated_filesystem():
            Path("edesto.toml").write_text('[serial]\nport = "/dev/ttyUSB0"\nbaud_rate = 9600\n')
            result = runner.invoke(main, ["config", "--list"])
            assert result.exit_code == 0
            assert "serial.port" in result.output
            assert "/dev/ttyUSB0" in result.output

    def test_set_config(self, runner):
        with runner.isolated_filesystem():
            Path("edesto.toml").write_text('[serial]\nport = "/dev/ttyUSB0"\n')
            result = runner.invoke(main, ["config", "debug.gpio", "25"])
            assert result.exit_code == 0
            content = Path("edesto.toml").read_text()
            assert "[debug]" in content
            assert "gpio = 25" in content

    def test_get_config(self, runner):
        with runner.isolated_filesystem():
            Path("edesto.toml").write_text('[serial]\nbaud_rate = 9600\n')
            result = runner.invoke(main, ["config", "serial.baud_rate"])
            assert result.exit_code == 0
            assert "9600" in result.output
