"""Tests for serial port utilities."""

from unittest.mock import patch, MagicMock

import pytest

from edesto_dev.serial.port import (
    PortInfo,
    SerialError,
    list_serial_ports,
    open_serial,
    resolve_port_and_baud,
)


class TestListSerialPorts:
    @patch("edesto_dev.serial.port.comports")
    def test_list_ports(self, mock_comports):
        port1 = MagicMock()
        port1.device = "/dev/ttyUSB0"
        port1.description = "CP2102 USB to UART Bridge"
        port1.hwid = "USB VID:PID=10C4:EA60"
        port2 = MagicMock()
        port2.device = "/dev/ttyACM0"
        port2.description = "Arduino Uno"
        port2.hwid = "USB VID:PID=2341:0043"
        mock_comports.return_value = [port1, port2]

        result = list_serial_ports()
        assert len(result) == 2
        assert result[0].device == "/dev/ttyUSB0"
        assert result[0].description == "CP2102 USB to UART Bridge"
        assert result[1].device == "/dev/ttyACM0"

    @patch("edesto_dev.serial.port.comports")
    def test_list_ports_empty(self, mock_comports):
        mock_comports.return_value = []
        result = list_serial_ports()
        assert result == []


class TestOpenSerial:
    @patch("edesto_dev.serial.port.serial.Serial")
    def test_open_success(self, mock_serial_class):
        mock_ser = MagicMock()
        mock_serial_class.return_value = mock_ser
        result = open_serial("/dev/ttyUSB0", 115200)
        assert result == mock_ser
        mock_serial_class.assert_called_once_with("/dev/ttyUSB0", 115200, timeout=1)

    @patch("edesto_dev.serial.port.serial.Serial")
    def test_open_not_found(self, mock_serial_class):
        import serial
        mock_serial_class.side_effect = serial.SerialException("could not open port")
        with pytest.raises(SerialError) as exc_info:
            open_serial("/dev/nonexistent", 115200)
        assert exc_info.value.exit_code == 2

    @patch("edesto_dev.serial.port.serial.Serial")
    def test_open_busy(self, mock_serial_class):
        import serial
        mock_serial_class.side_effect = serial.SerialException("Device or resource busy")
        with pytest.raises(SerialError) as exc_info:
            open_serial("/dev/ttyUSB0", 115200)
        assert exc_info.value.exit_code == 3

    @patch("edesto_dev.serial.port.serial.Serial")
    def test_open_permission_denied(self, mock_serial_class):
        mock_serial_class.side_effect = PermissionError("Permission denied")
        with pytest.raises(SerialError) as exc_info:
            open_serial("/dev/ttyUSB0", 115200)
        assert exc_info.value.exit_code == 4


class TestSerialError:
    def test_to_dict(self):
        err = SerialError("Port not found", exit_code=2)
        d = err.to_dict()
        assert d["error"] == "Port not found"
        assert d["exit_code"] == 2


class TestResolvePortAndBaud:
    def test_resolve_from_cli_flags(self, tmp_path):
        port, baud = resolve_port_and_baud("/dev/ttyUSB0", 9600, tmp_path)
        assert port == "/dev/ttyUSB0"
        assert baud == 9600

    def test_resolve_from_config(self, tmp_path):
        toml = tmp_path / "edesto.toml"
        toml.write_text('[serial]\nport = "/dev/ttyACM0"\nbaud_rate = 9600\n')
        port, baud = resolve_port_and_baud(None, None, tmp_path)
        assert port == "/dev/ttyACM0"
        assert baud == 9600

    def test_cli_overrides_config(self, tmp_path):
        toml = tmp_path / "edesto.toml"
        toml.write_text('[serial]\nport = "/dev/ttyACM0"\nbaud_rate = 9600\n')
        port, baud = resolve_port_and_baud("/dev/ttyUSB0", 115200, tmp_path)
        assert port == "/dev/ttyUSB0"
        assert baud == 115200

    def test_missing_port_raises(self, tmp_path):
        toml = tmp_path / "edesto.toml"
        toml.write_text('[serial]\nbaud_rate = 9600\n')
        with pytest.raises(Exception):
            resolve_port_and_baud(None, None, tmp_path)

    def test_missing_config_file_raises(self, tmp_path):
        with pytest.raises(Exception):
            resolve_port_and_baud(None, None, tmp_path)
