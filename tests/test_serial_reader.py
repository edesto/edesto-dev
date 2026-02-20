"""Tests for the serial reader/sender core."""

import time
from unittest.mock import MagicMock, PropertyMock

import pytest

from edesto_dev.serial.reader import (
    serial_read,
    serial_send,
    serial_monitor,
    ReadResult,
    SendResult,
)
from edesto_dev.serial.parser import LineParser, ParserConfig


class FakeSerial:
    """Fake serial port for testing."""

    def __init__(self, responses=None, delays=None):
        self._responses = list(responses or [])
        self._delays = list(delays or [])
        self._index = 0
        self._written = []
        self.is_open = True

    def readline(self):
        if self._index >= len(self._responses):
            # Simulate no more data (timeout)
            time.sleep(0.1)
            return b""
        if self._index < len(self._delays):
            time.sleep(self._delays[self._index])
        resp = self._responses[self._index]
        self._index += 1
        if isinstance(resp, str):
            return resp.encode()
        return resp

    def write(self, data):
        self._written.append(data)

    def flush(self):
        pass

    def close(self):
        self.is_open = False

    @property
    def in_waiting(self):
        return max(0, len(self._responses) - self._index)


class TestSerialRead:
    def test_basic_read(self):
        ser = FakeSerial(responses=["hello\n", "world\n", ""])
        result = serial_read(ser, duration=5)
        assert len(result.lines) == 2
        assert "hello" in result.lines[0]
        assert "world" in result.lines[1]

    def test_read_until_marker(self):
        ser = FakeSerial(responses=["line1\n", "line2\n", "[DONE]\n", "ignored\n"])
        result = serial_read(ser, until="[DONE]")
        assert result.exit_reason == "until_matched"
        assert any("[DONE]" in line for line in result.lines)

    def test_read_quiet_timeout(self):
        ser = FakeSerial(responses=["data\n", ""])
        result = serial_read(ser, duration=30, quiet_timeout=0.2)
        assert result.exit_reason == "quiet_timeout"
        assert len(result.lines) >= 1

    def test_read_duration_timeout(self):
        ser = FakeSerial(responses=["data\n"] * 100, delays=[0.05] * 100)
        result = serial_read(ser, duration=0.2)
        assert result.exit_reason == "duration"
        assert result.duration_seconds <= 1.0

    def test_read_with_parser(self):
        ser = FakeSerial(responses=["[SENSOR] temp=23.4\n", ""])
        config = ParserConfig(known_tags=["SENSOR"])
        parser = LineParser(config)
        result = serial_read(ser, duration=5, parser=parser, quiet_timeout=0.2)
        assert len(result.parsed_lines) >= 1
        assert result.parsed_lines[0].tag == "SENSOR"

    def test_read_log_path(self, tmp_path):
        ser = FakeSerial(responses=["log line\n", ""])
        log_path = tmp_path / "test.jsonl"
        result = serial_read(ser, duration=5, log_path=log_path, quiet_timeout=0.2)
        assert log_path.exists()
        content = log_path.read_text()
        assert "log line" in content


class TestSerialSend:
    def test_send_basic(self):
        ser = FakeSerial(responses=["[OK]\n", ""])
        result = serial_send(ser, "test_cmd", quiet_timeout=0.2)
        assert b"test_cmd" in ser._written[0]
        assert result.exit_code == 0

    def test_send_with_echo_stripping(self):
        ser = FakeSerial(responses=["test_cmd\n", "response\n", ""])
        result = serial_send(ser, "test_cmd", strip_echo=True, quiet_timeout=0.2)
        # Echo line should be stripped
        assert not any("test_cmd" == line.strip() for line in result.lines)

    def test_send_quiet_timeout(self):
        ser = FakeSerial(responses=["some response\n", ""])
        result = serial_send(ser, "cmd", quiet_timeout=0.2)
        assert result.exit_reason in ("quiet_timeout", "until_matched")

    def test_send_with_success_marker(self):
        ser = FakeSerial(responses=["processing...\n", "[OK]\n", ""])
        result = serial_send(ser, "cmd", success_markers=["[OK]"])
        assert result.exit_code == 0
        assert result.exit_reason == "success_marker"

    def test_send_with_error_marker(self):
        ser = FakeSerial(responses=["processing...\n", "[ERROR] failed\n", ""])
        result = serial_send(ser, "cmd", error_markers=["[ERROR]"])
        assert result.exit_code == 1
        assert result.was_error is True

    def test_send_boot_wait_timeout_proceeds(self):
        # No [READY] in responses — should proceed after timeout
        ser = FakeSerial(responses=["some output\n", ""])
        result = serial_send(
            ser, "cmd",
            wait_ready="[READY]",
            ready_timeout=0.2,
            quiet_timeout=0.2,
        )
        # Should still have sent the command (proceeded after timeout)
        assert len(ser._written) > 0

    def test_send_log_file(self, tmp_path):
        ser = FakeSerial(responses=["response\n", ""])
        log_path = tmp_path / "send.jsonl"
        result = serial_send(ser, "cmd", log_path=log_path, quiet_timeout=0.2)
        assert log_path.exists()


class TestSerialMonitor:
    def test_monitor_duration(self):
        ser = FakeSerial(responses=["line1\n"] * 20, delays=[0.05] * 20)
        lines_received = []

        def callback(line):
            lines_received.append(line)

        serial_monitor(ser, duration=0.2, output_callback=callback)
        assert len(lines_received) >= 1

    def test_monitor_log_path(self, tmp_path):
        ser = FakeSerial(responses=["monitor line\n", ""])
        log_path = tmp_path / "monitor.jsonl"
        serial_monitor(ser, duration=0.3, log_path=log_path)
        assert log_path.exists()


class TestReadResult:
    def test_attributes(self):
        result = ReadResult(
            lines=["a", "b"],
            parsed_lines=[],
            duration_seconds=1.5,
            exit_reason="duration",
        )
        assert len(result.lines) == 2
        assert result.duration_seconds == 1.5
        assert result.exit_reason == "duration"


class TestSendResult:
    def test_attributes(self):
        result = SendResult(
            lines=["response"],
            parsed_lines=[],
            duration_seconds=0.5,
            exit_reason="success_marker",
            exit_code=0,
            was_error=False,
        )
        assert result.exit_code == 0
        assert result.was_error is False
