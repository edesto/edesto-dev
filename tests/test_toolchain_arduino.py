"""Tests for the Arduino toolchain."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from edesto_dev.toolchains.arduino import ArduinoToolchain


@pytest.fixture
def arduino():
    return ArduinoToolchain()


class TestArduinoToolchainBasics:
    def test_name(self, arduino):
        assert arduino.name == "arduino"

    def test_list_boards_returns_17(self, arduino):
        boards = arduino.list_boards()
        assert len(boards) == 17

    def test_get_board_esp32(self, arduino):
        board = arduino.get_board("esp32")
        assert board is not None
        assert board.name == "ESP32"
        assert board.baud_rate == 115200

    def test_get_board_arduino_uno(self, arduino):
        board = arduino.get_board("arduino-uno")
        assert board is not None
        assert board.baud_rate == 9600

    def test_get_board_unknown(self, arduino):
        assert arduino.get_board("nonexistent") is None

    def test_all_board_slugs(self, arduino):
        expected = [
            "esp32", "esp32s3", "esp32c3", "esp32c6", "esp8266",
            "arduino-uno", "arduino-nano", "arduino-mega",
            "rp2040", "teensy40", "teensy41", "stm32-nucleo",
            "stm32f4-discovery", "stm32h7-nucleo", "stm32l4-nucleo",
            "nrf52840", "nrf5340",
        ]
        slugs = [b.slug for b in arduino.list_boards()]
        for s in expected:
            assert s in slugs, f"Missing board: {s}"


class TestArduinoCommands:
    def test_compile_command(self, arduino):
        board = arduino.get_board("esp32")
        cmd = arduino.compile_command(board)
        assert "arduino-cli compile" in cmd
        assert "esp32:esp32:esp32" in cmd

    def test_upload_command(self, arduino):
        board = arduino.get_board("esp32")
        cmd = arduino.upload_command(board, "/dev/ttyUSB0")
        assert "arduino-cli upload" in cmd
        assert "esp32:esp32:esp32" in cmd
        assert "/dev/ttyUSB0" in cmd

    def test_monitor_command(self, arduino):
        board = arduino.get_board("esp32")
        cmd = arduino.monitor_command(board, "/dev/ttyUSB0")
        assert "arduino-cli monitor" in cmd or "monitor" in cmd
        assert "/dev/ttyUSB0" in cmd


class TestArduinoDetectProject:
    def test_detects_ino_file(self, arduino, tmp_path):
        (tmp_path / "sketch.ino").write_text("void setup() {}")
        assert arduino.detect_project(tmp_path) is True

    def test_no_ino_file(self, arduino, tmp_path):
        (tmp_path / "main.py").write_text("print('hi')")
        assert arduino.detect_project(tmp_path) is False


class TestArduinoDetectBoards:
    ARDUINO_CLI_ONE_BOARD = json.dumps({
        "detected_ports": [{
            "matching_boards": [{"name": "ESP32 Dev Module", "fqbn": "esp32:esp32:esp32"}],
            "port": {"address": "/dev/cu.usbserial-0001", "protocol": "serial"},
        }]
    })

    ARDUINO_CLI_CH340_NO_MATCH = json.dumps({
        "detected_ports": [{
            "port": {
                "address": "/dev/cu.usbserial-110",
                "protocol": "serial",
                "properties": {"pid": "0x7523", "vid": "0x1A86"},
            }
        }]
    })

    @patch("edesto_dev.toolchains.arduino.subprocess.run")
    def test_detects_board(self, mock_run, arduino):
        mock = MagicMock()
        mock.stdout = self.ARDUINO_CLI_ONE_BOARD
        mock.returncode = 0
        mock_run.return_value = mock
        detected = arduino.detect_boards()
        assert len(detected) == 1
        assert detected[0].board.slug == "esp32"
        assert detected[0].port == "/dev/cu.usbserial-0001"
        assert detected[0].toolchain_name == "arduino"

    @patch("edesto_dev.toolchains.arduino.subprocess.run", side_effect=FileNotFoundError)
    def test_no_arduino_cli(self, mock_run, arduino):
        assert arduino.detect_boards() == []

    @patch("edesto_dev.toolchains.arduino.subprocess.run")
    def test_vid_pid_fallback(self, mock_run, arduino):
        mock = MagicMock()
        mock.stdout = self.ARDUINO_CLI_CH340_NO_MATCH
        mock.returncode = 0
        mock_run.return_value = mock
        detected = arduino.detect_boards()
        slugs = [d.board.slug for d in detected]
        assert "esp32" in slugs


class TestArduinoDoctor:
    @patch("shutil.which", return_value="/usr/local/bin/arduino-cli")
    def test_doctor_ok(self, mock_which, arduino):
        result = arduino.doctor()
        assert result["ok"] is True

    @patch("shutil.which", return_value=None)
    def test_doctor_missing(self, mock_which, arduino):
        result = arduino.doctor()
        assert result["ok"] is False


class TestArduinoSerialConfig:
    def test_esp32_config(self, arduino):
        board = arduino.get_board("esp32")
        config = arduino.serial_config(board)
        assert config["baud_rate"] == 115200
        assert config["boot_delay"] == 3

    def test_uno_config(self, arduino):
        board = arduino.get_board("arduino-uno")
        config = arduino.serial_config(board)
        assert config["baud_rate"] == 9600


class TestBoardOpenocdTargets:
    def test_stm32_nucleo_has_openocd_target(self, arduino):
        board = arduino.get_board("stm32-nucleo")
        assert board.openocd_target == "stm32f4x"

    def test_esp32_has_openocd_target(self, arduino):
        board = arduino.get_board("esp32")
        assert board.openocd_target == "esp32"

    def test_rp2040_has_openocd_target(self, arduino):
        board = arduino.get_board("rp2040")
        assert board.openocd_target == "rp2040"

    def test_arduino_uno_has_no_openocd_target(self, arduino):
        board = arduino.get_board("arduino-uno")
        assert board.openocd_target == ""
