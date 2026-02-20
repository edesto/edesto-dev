"""Tests for the debug status assembly module."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from edesto_dev.debug.status import (
    collect_status,
    DebugStatus,
    _analyze_serial_log,
)


def _setup_project(tmp_path, *, scan_data=None, manifest_data=None, log_lines=None, toml_content=None):
    """Helper to set up a project directory with optional state files."""
    edesto_dir = tmp_path / ".edesto"
    edesto_dir.mkdir(exist_ok=True)
    (edesto_dir / ".gitignore").write_text("*\n")

    if scan_data is not None:
        (edesto_dir / "debug-scan.json").write_text(json.dumps(scan_data))

    if manifest_data is not None:
        (edesto_dir / "instrument-manifest.json").write_text(json.dumps(manifest_data))

    if log_lines is not None:
        log_path = edesto_dir / "debug-log.jsonl"
        with open(log_path, "w") as f:
            for entry in log_lines:
                f.write(json.dumps(entry) + "\n")

    if toml_content is not None:
        (tmp_path / "edesto.toml").write_text(toml_content)


def _make_scan_data(**overrides):
    """Create a default scan data dict with overrides."""
    data = {
        "serial": {
            "boot_marker": None,
            "success_markers": [],
            "error_markers": [],
            "echo": False,
            "prompt": None,
            "line_terminator": "\n",
            "known_commands": [],
            "baud_rate": None,
        },
        "logging_api": {
            "primary": "printf",
            "variants": [],
            "tag_convention": None,
            "examples": [],
        },
        "danger_zones": [],
        "safe_zones": [],
    }
    for k, v in overrides.items():
        if k in data:
            if isinstance(data[k], dict) and isinstance(v, dict):
                data[k].update(v)
            else:
                data[k] = v
    return data


class TestCollectStatusFull:
    def test_full_status_with_all_data(self, tmp_path):
        scan_data = _make_scan_data(
            serial={
                "boot_marker": "[READY]",
                "success_markers": ["[OK]"],
                "error_markers": ["[ERROR]"],
                "echo": False,
                "prompt": None,
                "line_terminator": "\n",
                "known_commands": [{"command": "status", "args": None, "file": "main.c", "line": 10}],
                "baud_rate": 115200,
            },
            danger_zones=[{"file": "main.c", "function": "my_isr", "line_range": [1, 3], "reason": "ISR"}],
            safe_zones=[{"file": "main.c", "function": "setup", "line_range": [5, 20]}],
        )
        manifest_data = {
            "entries": [
                {"file": "main.c", "line": 10, "content": "printf debug", "timestamp": "2024-01-01T00:00:00Z"},
                {"file": "util.c", "line": 5, "content": "printf debug2", "timestamp": "2024-01-01T00:01:00Z"},
            ]
        }
        log_lines = [
            {"ts": "2024-01-01T00:00:00Z", "raw": "[READY]", "tag": "READY", "data": {}},
            {"ts": "2024-01-01T00:00:01Z", "raw": "val=42", "tag": None, "data": {"val": "42"}},
            {"ts": "2024-01-01T00:00:02Z", "raw": "[ERROR] something failed", "tag": "ERROR", "data": {"message": "something failed"}},
            {"ts": "2024-01-01T00:00:03Z", "raw": "val=100", "tag": None, "data": {"val": "100"}},
        ]
        _setup_project(tmp_path, scan_data=scan_data, manifest_data=manifest_data, log_lines=log_lines,
                       toml_content='[serial]\nport = "/dev/ttyUSB0"\nbaud_rate = 115200\n')

        status = collect_status(tmp_path)
        assert isinstance(status, DebugStatus)

        # Serial log analysis
        assert status.serial_log["total_lines"] == 4
        assert status.serial_log["resets_detected"] == 1  # one boot marker

        # Project info
        assert status.project["logging_api"] == "printf"
        assert len(status.project["danger_zones"]) == 1
        assert len(status.project["safe_zones"]) == 1

        # Serial config
        assert status.serial["boot_marker"] == "[READY]"

        # Instrumentation
        assert status.instrumentation["active_count"] == 2
        assert set(status.instrumentation["files_modified"]) == {"main.c", "util.c"}

    def test_status_with_empty_log(self, tmp_path):
        scan_data = _make_scan_data()
        _setup_project(tmp_path, scan_data=scan_data)

        status = collect_status(tmp_path)
        assert status.serial_log["total_lines"] == 0
        assert status.serial_log["resets_detected"] == 0
        assert status.serial_log["errors"] == []

    def test_status_with_no_scan(self, tmp_path):
        _setup_project(tmp_path)

        status = collect_status(tmp_path)
        assert status.serial is None
        assert status.project["logging_api"] is None
        assert status.project["danger_zones"] == []

    def test_status_with_no_boot_marker(self, tmp_path):
        scan_data = _make_scan_data()  # boot_marker is None
        log_lines = [
            {"ts": "2024-01-01T00:00:00Z", "raw": "hello", "tag": None, "data": {}},
        ]
        _setup_project(tmp_path, scan_data=scan_data, log_lines=log_lines)

        status = collect_status(tmp_path)
        assert status.device["boot_count_in_session"] == 0
        assert status.device["uptime_estimate_seconds"] is None


class TestLogAnalysis:
    def test_error_aggregation(self, tmp_path):
        log_lines = [
            {"ts": "2024-01-01T00:00:01Z", "raw": "[ERROR] timeout", "tag": "ERROR", "data": {"message": "timeout"}},
            {"ts": "2024-01-01T00:00:02Z", "raw": "[ERROR] timeout", "tag": "ERROR", "data": {"message": "timeout"}},
            {"ts": "2024-01-01T00:00:03Z", "raw": "[ERROR] bad data", "tag": "ERROR", "data": {"message": "bad data"}},
        ]
        _setup_project(tmp_path, log_lines=log_lines)
        log_path = tmp_path / ".edesto" / "debug-log.jsonl"

        result = _analyze_serial_log(log_path, boot_marker=None)
        assert result["total_lines"] == 3
        # Errors grouped by raw message
        assert len(result["errors"]) == 2
        timeout_err = next(e for e in result["errors"] if "timeout" in e["message"])
        assert timeout_err["count"] == 2
        assert timeout_err["first_ts"] == "2024-01-01T00:00:01Z"
        assert timeout_err["last_ts"] == "2024-01-01T00:00:02Z"

    def test_value_tracking(self, tmp_path):
        log_lines = [
            {"ts": "2024-01-01T00:00:01Z", "raw": "temp=25", "tag": None, "data": {"temp": "25"}},
            {"ts": "2024-01-01T00:00:02Z", "raw": "temp=30", "tag": None, "data": {"temp": "30"}},
            {"ts": "2024-01-01T00:00:03Z", "raw": "temp=20", "tag": None, "data": {"temp": "20"}},
        ]
        _setup_project(tmp_path, log_lines=log_lines)
        log_path = tmp_path / ".edesto" / "debug-log.jsonl"

        result = _analyze_serial_log(log_path, boot_marker=None)
        assert "temp" in result["values"]
        assert result["values"]["temp"]["min"] == 20
        assert result["values"]["temp"]["max"] == 30
        assert result["values"]["temp"]["last"] == 20
        assert result["values"]["temp"]["count"] == 3

    def test_boot_marker_counting(self, tmp_path):
        log_lines = [
            {"ts": "2024-01-01T00:00:00Z", "raw": "[READY]", "tag": None, "data": {}},
            {"ts": "2024-01-01T00:00:01Z", "raw": "hello", "tag": None, "data": {}},
            {"ts": "2024-01-01T00:00:05Z", "raw": "[READY]", "tag": None, "data": {}},
            {"ts": "2024-01-01T00:00:06Z", "raw": "world", "tag": None, "data": {}},
        ]
        _setup_project(tmp_path, log_lines=log_lines)
        log_path = tmp_path / ".edesto" / "debug-log.jsonl"

        result = _analyze_serial_log(log_path, boot_marker="[READY]")
        assert result["resets_detected"] == 2

    def test_empty_log(self, tmp_path):
        _setup_project(tmp_path)
        log_path = tmp_path / ".edesto" / "debug-log.jsonl"
        # Doesn't exist
        result = _analyze_serial_log(log_path, boot_marker=None)
        assert result["total_lines"] == 0
        assert result["errors"] == []
        assert result["values"] == {}

    def test_tags_seen(self, tmp_path):
        log_lines = [
            {"ts": "2024-01-01T00:00:00Z", "raw": "[READY]", "tag": "READY", "data": {}},
            {"ts": "2024-01-01T00:00:01Z", "raw": "hello", "tag": None, "data": {}},
            {"ts": "2024-01-01T00:00:02Z", "raw": "[ERROR] x", "tag": "ERROR", "data": {}},
            {"ts": "2024-01-01T00:00:03Z", "raw": "[READY]", "tag": "READY", "data": {}},
        ]
        _setup_project(tmp_path, log_lines=log_lines)
        log_path = tmp_path / ".edesto" / "debug-log.jsonl"

        result = _analyze_serial_log(log_path, boot_marker="[READY]")
        assert "READY" in result["tags_seen"]
        assert "ERROR" in result["tags_seen"]


class TestDebugStatusSerialization:
    def test_to_dict_roundtrip(self, tmp_path):
        scan_data = _make_scan_data(
            serial={"boot_marker": "[READY]", "success_markers": ["[OK]"],
                    "error_markers": ["[ERROR]"], "echo": False,
                    "prompt": None, "line_terminator": "\n",
                    "known_commands": [], "baud_rate": 115200},
        )
        _setup_project(tmp_path, scan_data=scan_data)

        status = collect_status(tmp_path)
        d = status.to_dict()
        assert isinstance(d, dict)
        assert "serial_log" in d
        assert "serial" in d
        assert "project" in d
        assert "instrumentation" in d
        assert "device" in d

    def test_to_human_format(self, tmp_path):
        scan_data = _make_scan_data(
            serial={"boot_marker": "[READY]", "success_markers": ["[OK]"],
                    "error_markers": ["[ERROR]"], "echo": False,
                    "prompt": None, "line_terminator": "\n",
                    "known_commands": [], "baud_rate": 115200},
        )
        log_lines = [
            {"ts": "2024-01-01T00:00:00Z", "raw": "[READY]", "tag": "READY", "data": {}},
            {"ts": "2024-01-01T00:00:01Z", "raw": "val=42", "tag": None, "data": {"val": "42"}},
        ]
        _setup_project(tmp_path, scan_data=scan_data, log_lines=log_lines)

        status = collect_status(tmp_path)
        text = status.to_human()
        assert isinstance(text, str)
        assert "Serial Log" in text
        assert "total_lines" in text or "lines" in text.lower()

    def test_to_human_no_boot_marker(self, tmp_path):
        scan_data = _make_scan_data()  # boot_marker=None
        _setup_project(tmp_path, scan_data=scan_data)

        status = collect_status(tmp_path)
        text = status.to_human()
        assert "N/A" in text


class TestDetectGdb:
    def test_esp32_xtensa(self):
        from edesto_dev.debug.status import _detect_gdb_binary
        assert _detect_gdb_binary("ESP32 DevKit") == "xtensa-esp-elf-gdb"

    def test_esp32_c3_riscv(self):
        from edesto_dev.debug.status import _detect_gdb_binary
        assert _detect_gdb_binary("ESP32-C3") == "riscv32-esp-elf-gdb"

    def test_arm_board(self):
        from edesto_dev.debug.status import _detect_gdb_binary
        assert _detect_gdb_binary("STM32F4") == "arm-none-eabi-gdb"

    def test_none_board(self):
        from edesto_dev.debug.status import _detect_gdb_binary
        assert _detect_gdb_binary(None) is None


class TestStatusCLI:
    def test_status_json(self, tmp_path):
        from click.testing import CliRunner
        from edesto_dev.cli import main

        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            edesto_dir = Path(td) / ".edesto"
            edesto_dir.mkdir()
            (edesto_dir / ".gitignore").write_text("*\n")
            scan_data = _make_scan_data()
            (edesto_dir / "debug-scan.json").write_text(json.dumps(scan_data))

            result = runner.invoke(main, ["debug", "status", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert "serial_log" in data
            assert "project" in data

    def test_status_human(self, tmp_path):
        from click.testing import CliRunner
        from edesto_dev.cli import main

        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            edesto_dir = Path(td) / ".edesto"
            edesto_dir.mkdir()
            (edesto_dir / ".gitignore").write_text("*\n")
            scan_data = _make_scan_data()
            (edesto_dir / "debug-scan.json").write_text(json.dumps(scan_data))

            result = runner.invoke(main, ["debug", "status"])
            assert result.exit_code == 0
            assert "Serial Log" in result.output or "Debug Status" in result.output
