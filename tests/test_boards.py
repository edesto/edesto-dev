"""Tests for board definitions (via Arduino toolchain)."""

import json
from unittest.mock import patch, MagicMock

import pytest
from edesto_dev.toolchains.arduino import ArduinoToolchain


@pytest.fixture
def arduino():
    return ArduinoToolchain()


class TestGetBoard:
    def test_esp32_returns_correct_fqbn(self, arduino):
        board = arduino.get_board("esp32")
        assert board.fqbn == "esp32:esp32:esp32:UploadSpeed=115200"

    def test_esp32_has_name(self, arduino):
        board = arduino.get_board("esp32")
        assert board.name == "ESP32"

    def test_esp32_has_core(self, arduino):
        board = arduino.get_board("esp32")
        assert board.core == "esp32:esp32"

    def test_esp32_has_baud_rate(self, arduino):
        board = arduino.get_board("esp32")
        assert board.baud_rate == 115200

    def test_esp32_has_capabilities(self, arduino):
        board = arduino.get_board("esp32")
        assert "wifi" in board.capabilities
        assert "bluetooth" in board.capabilities

    def test_esp32_has_pins(self, arduino):
        board = arduino.get_board("esp32")
        assert "onboard_led" in board.pins
        assert board.pins["onboard_led"] == 2

    def test_esp32_has_pitfalls(self, arduino):
        board = arduino.get_board("esp32")
        assert len(board.pitfalls) > 0
        assert any("ADC2" in p for p in board.pitfalls)

    def test_unknown_board_returns_none(self, arduino):
        assert arduino.get_board("nonexistent") is None


class TestListBoards:
    def test_returns_list(self, arduino):
        boards = arduino.list_boards()
        assert isinstance(boards, list)
        assert len(boards) > 0

    def test_esp32_in_list(self, arduino):
        boards = arduino.list_boards()
        slugs = [b.slug for b in boards]
        assert "esp32" in slugs


ALL_BOARD_SLUGS = [
    "esp32", "esp32s3", "esp32c3", "esp32c6",
    "esp8266",
    "arduino-uno", "arduino-nano", "arduino-mega",
    "rp2040",
    "teensy40", "teensy41",
    "stm32-nucleo",
]


class TestAllBoards:
    def test_all_boards_registered(self, arduino):
        boards = arduino.list_boards()
        slugs = [b.slug for b in boards]
        for expected in ALL_BOARD_SLUGS:
            assert expected in slugs, f"Missing board: {expected}"

    def test_total_board_count(self, arduino):
        assert len(arduino.list_boards()) == 12

    @pytest.mark.parametrize("slug", ALL_BOARD_SLUGS)
    def test_board_has_required_fields(self, slug, arduino):
        board = arduino.get_board(slug)
        assert board is not None, f"Board {slug} not found"
        assert board.name, f"{slug} missing name"
        assert board.fqbn, f"{slug} missing fqbn"
        assert board.core, f"{slug} missing core"
        assert board.baud_rate > 0, f"{slug} missing baud_rate"
        assert len(board.pitfalls) > 0, f"{slug} missing pitfalls"
        assert len(board.pin_notes) > 0, f"{slug} missing pin_notes"

    @pytest.mark.parametrize("slug", ["esp32", "esp32s3", "esp32c3", "esp32c6", "esp8266"])
    def test_wifi_boards_have_wifi_capability(self, slug, arduino):
        board = arduino.get_board(slug)
        assert "wifi" in board.capabilities

    @pytest.mark.parametrize("slug", ["arduino-uno", "arduino-nano", "arduino-mega", "rp2040"])
    def test_basic_boards_no_wifi(self, slug, arduino):
        board = arduino.get_board(slug)
        assert "wifi" not in board.capabilities

    @pytest.mark.parametrize("slug", ALL_BOARD_SLUGS)
    def test_board_fqbn_format(self, slug, arduino):
        board = arduino.get_board(slug)
        parts = board.fqbn.split(":")
        assert len(parts) >= 3, f"{slug} FQBN should have at least 3 colon-separated parts"


class TestGetBoardByFqbn:
    def test_finds_esp32(self, arduino):
        board = arduino._get_board_by_fqbn("esp32:esp32:esp32")
        assert board.slug == "esp32"

    def test_finds_arduino_uno(self, arduino):
        board = arduino._get_board_by_fqbn("arduino:avr:uno")
        assert board.slug == "arduino-uno"

    def test_unknown_fqbn_returns_none(self, arduino):
        assert arduino._get_board_by_fqbn("unknown:unknown:unknown") is None

    @pytest.mark.parametrize("slug", ALL_BOARD_SLUGS)
    def test_all_boards_findable_by_fqbn(self, slug, arduino):
        board = arduino.get_board(slug)
        found = arduino._get_board_by_fqbn(board.fqbn)
        assert found is not None
        assert found.slug == slug


# Sample arduino-cli board list JSON (modern format)
ARDUINO_CLI_ONE_BOARD = json.dumps({
    "detected_ports": [
        {
            "matching_boards": [
                {"name": "ESP32 Dev Module", "fqbn": "esp32:esp32:esp32"}
            ],
            "port": {
                "address": "/dev/cu.usbserial-0001",
                "label": "/dev/cu.usbserial-0001",
                "protocol": "serial",
                "protocol_label": "Serial Port (USB)",
            },
        }
    ]
})

ARDUINO_CLI_TWO_BOARDS = json.dumps({
    "detected_ports": [
        {
            "matching_boards": [
                {"name": "ESP32 Dev Module", "fqbn": "esp32:esp32:esp32"}
            ],
            "port": {
                "address": "/dev/cu.usbserial-0001",
                "protocol": "serial",
            },
        },
        {
            "matching_boards": [
                {"name": "Arduino Uno", "fqbn": "arduino:avr:uno"}
            ],
            "port": {
                "address": "/dev/ttyACM0",
                "protocol": "serial",
            },
        },
    ]
})

ARDUINO_CLI_NO_BOARDS = json.dumps({"detected_ports": []})

ARDUINO_CLI_UNRECOGNIZED = json.dumps({
    "detected_ports": [
        {
            "matching_boards": [],
            "port": {
                "address": "/dev/ttyUSB0",
                "protocol": "serial",
            },
        }
    ]
})

# CH340 port with no matching_boards (typical ESP32 via generic USB-serial)
ARDUINO_CLI_CH340_NO_MATCH = json.dumps({
    "detected_ports": [
        {
            "port": {
                "address": "/dev/cu.usbserial-110",
                "protocol": "serial",
                "protocol_label": "Serial Port (USB)",
                "properties": {"pid": "0x7523", "vid": "0x1A86"},
            }
        }
    ]
})

# CH340 port with FQBN match (FQBN should take priority over VID/PID)
ARDUINO_CLI_CH340_WITH_FQBN = json.dumps({
    "detected_ports": [
        {
            "matching_boards": [
                {"name": "ESP32 Dev Module", "fqbn": "esp32:esp32:esp32"}
            ],
            "port": {
                "address": "/dev/cu.usbserial-110",
                "protocol": "serial",
                "properties": {"pid": "0x7523", "vid": "0x1A86"},
            },
        }
    ]
})

# Unknown VID/PID, no matching_boards
ARDUINO_CLI_UNKNOWN_VID_PID = json.dumps({
    "detected_ports": [
        {
            "port": {
                "address": "/dev/ttyUSB0",
                "protocol": "serial",
                "properties": {"pid": "0xFFFF", "vid": "0xFFFF"},
            }
        }
    ]
})

# CH340 with lowercase VID/PID
ARDUINO_CLI_CH340_LOWERCASE = json.dumps({
    "detected_ports": [
        {
            "port": {
                "address": "/dev/cu.usbserial-110",
                "protocol": "serial",
                "properties": {"pid": "0x7523", "vid": "0x1a86"},
            }
        }
    ]
})


def _mock_subprocess(stdout, returncode=0):
    mock = MagicMock()
    mock.stdout = stdout
    mock.returncode = returncode
    return mock


class TestDetectBoards:
    @patch("edesto_dev.toolchains.arduino.subprocess.run")
    def test_detects_one_board(self, mock_run, arduino):
        mock_run.return_value = _mock_subprocess(ARDUINO_CLI_ONE_BOARD)
        detected = arduino.detect_boards()
        assert len(detected) == 1
        assert detected[0].board.slug == "esp32"
        assert detected[0].port == "/dev/cu.usbserial-0001"

    @patch("edesto_dev.toolchains.arduino.subprocess.run")
    def test_detects_two_boards(self, mock_run, arduino):
        mock_run.return_value = _mock_subprocess(ARDUINO_CLI_TWO_BOARDS)
        detected = arduino.detect_boards()
        assert len(detected) == 2
        slugs = [d.board.slug for d in detected]
        assert "esp32" in slugs
        assert "arduino-uno" in slugs

    @patch("edesto_dev.toolchains.arduino.subprocess.run")
    def test_no_boards_returns_empty(self, mock_run, arduino):
        mock_run.return_value = _mock_subprocess(ARDUINO_CLI_NO_BOARDS)
        detected = arduino.detect_boards()
        assert detected == []

    @patch("edesto_dev.toolchains.arduino.subprocess.run")
    def test_unrecognized_board_skipped(self, mock_run, arduino):
        mock_run.return_value = _mock_subprocess(ARDUINO_CLI_UNRECOGNIZED)
        detected = arduino.detect_boards()
        assert detected == []

    @patch("edesto_dev.toolchains.arduino.subprocess.run", side_effect=FileNotFoundError)
    def test_arduino_cli_not_installed(self, mock_run, arduino):
        detected = arduino.detect_boards()
        assert detected == []

    @patch("edesto_dev.toolchains.arduino.subprocess.run")
    def test_arduino_cli_fails(self, mock_run, arduino):
        mock_run.return_value = _mock_subprocess("", returncode=1)
        detected = arduino.detect_boards()
        assert detected == []

    @patch("edesto_dev.toolchains.arduino.subprocess.run")
    def test_vid_pid_fallback_ch340(self, mock_run, arduino):
        mock_run.return_value = _mock_subprocess(ARDUINO_CLI_CH340_NO_MATCH)
        detected = arduino.detect_boards()
        slugs = [d.board.slug for d in detected]
        assert "esp32" in slugs
        assert "esp8266" in slugs
        assert "arduino-nano" in slugs
        assert all(d.port == "/dev/cu.usbserial-110" for d in detected)

    @patch("edesto_dev.toolchains.arduino.subprocess.run")
    def test_fqbn_takes_priority_over_vid_pid(self, mock_run, arduino):
        mock_run.return_value = _mock_subprocess(ARDUINO_CLI_CH340_WITH_FQBN)
        detected = arduino.detect_boards()
        assert len(detected) == 1
        assert detected[0].board.slug == "esp32"

    @patch("edesto_dev.toolchains.arduino.subprocess.run")
    def test_unknown_vid_pid_returns_empty(self, mock_run, arduino):
        mock_run.return_value = _mock_subprocess(ARDUINO_CLI_UNKNOWN_VID_PID)
        detected = arduino.detect_boards()
        assert detected == []

    @patch("edesto_dev.toolchains.arduino.subprocess.run")
    def test_vid_pid_case_insensitive(self, mock_run, arduino):
        mock_run.return_value = _mock_subprocess(ARDUINO_CLI_CH340_LOWERCASE)
        detected = arduino.detect_boards()
        slugs = [d.board.slug for d in detected]
        assert "esp32" in slugs
        assert "esp8266" in slugs
        assert "arduino-nano" in slugs
