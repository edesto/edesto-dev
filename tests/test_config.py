"""Tests for the config and state layer."""

import json
from pathlib import Path

import pytest

from edesto_dev.config import (
    ProjectConfig,
    SerialConfig,
    DebugConfig,
    load_project_config,
    get_config_value,
    set_config_value,
    list_config,
    ensure_edesto_dir,
    load_scan_cache,
    save_scan_cache,
    load_instrument_manifest,
    save_instrument_manifest,
    append_debug_log,
    clear_debug_state,
)


class TestLoadProjectConfig:
    def test_load_minimal_toml(self, tmp_path):
        toml = tmp_path / "edesto.toml"
        toml.write_text('[serial]\nport = "/dev/ttyUSB0"\nbaud_rate = 115200\n')
        config = load_project_config(tmp_path)
        assert config.serial.port == "/dev/ttyUSB0"
        assert config.serial.baud_rate == 115200

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_project_config(tmp_path)

    def test_missing_sections_get_defaults(self, tmp_path):
        toml = tmp_path / "edesto.toml"
        toml.write_text('[serial]\nport = "/dev/ttyUSB0"\n')
        config = load_project_config(tmp_path)
        assert config.debug.gpio is None
        assert config.serial.baud_rate == 115200  # default

    def test_debug_section(self, tmp_path):
        toml = tmp_path / "edesto.toml"
        toml.write_text('[debug]\ngpio = 25\n')
        config = load_project_config(tmp_path)
        assert config.debug.gpio == 25

    def test_toolchain_section(self, tmp_path):
        toml = tmp_path / "edesto.toml"
        toml.write_text('[toolchain]\nname = "custom"\ncompile = "make build"\nupload = "make flash"\n')
        config = load_project_config(tmp_path)
        assert config.toolchain["name"] == "custom"
        assert config.toolchain["compile"] == "make build"

    def test_jtag_section(self, tmp_path):
        toml = tmp_path / "edesto.toml"
        toml.write_text('[jtag]\ninterface = "stlink"\ntarget = "stm32f4x"\n')
        config = load_project_config(tmp_path)
        assert config.jtag["interface"] == "stlink"
        assert config.jtag["target"] == "stm32f4x"

    def test_empty_toml(self, tmp_path):
        toml = tmp_path / "edesto.toml"
        toml.write_text("")
        config = load_project_config(tmp_path)
        assert config.serial.port is None
        assert config.serial.baud_rate == 115200
        assert config.debug.gpio is None


class TestGetConfigValue:
    def test_dotted_key(self, tmp_path):
        toml = tmp_path / "edesto.toml"
        toml.write_text('[serial]\nbaud_rate = 9600\n')
        assert get_config_value(tmp_path, "serial.baud_rate") == 9600

    def test_missing_key_returns_none(self, tmp_path):
        toml = tmp_path / "edesto.toml"
        toml.write_text('[serial]\nport = "/dev/ttyUSB0"\n')
        assert get_config_value(tmp_path, "debug.gpio") is None

    def test_debug_gpio(self, tmp_path):
        toml = tmp_path / "edesto.toml"
        toml.write_text('[debug]\ngpio = 25\n')
        assert get_config_value(tmp_path, "debug.gpio") == 25


class TestSetConfigValue:
    def test_set_creates_section(self, tmp_path):
        toml = tmp_path / "edesto.toml"
        toml.write_text('[serial]\nport = "/dev/ttyUSB0"\n')
        set_config_value(tmp_path, "debug.gpio", 25)
        content = toml.read_text()
        assert "[debug]" in content
        assert "gpio = 25" in content

    def test_set_updates_existing(self, tmp_path):
        toml = tmp_path / "edesto.toml"
        toml.write_text('[serial]\nbaud_rate = 9600\n')
        set_config_value(tmp_path, "serial.baud_rate", 115200)
        content = toml.read_text()
        assert "115200" in content
        assert "9600" not in content

    def test_set_integer_coercion(self, tmp_path):
        toml = tmp_path / "edesto.toml"
        toml.write_text("")
        set_config_value(tmp_path, "debug.gpio", "25")
        content = toml.read_text()
        assert "gpio = 25" in content

    def test_set_string_value(self, tmp_path):
        toml = tmp_path / "edesto.toml"
        toml.write_text("")
        set_config_value(tmp_path, "serial.port", "/dev/ttyUSB0")
        content = toml.read_text()
        assert 'port = "/dev/ttyUSB0"' in content

    def test_set_creates_file_if_missing(self, tmp_path):
        set_config_value(tmp_path, "debug.gpio", 25)
        toml = tmp_path / "edesto.toml"
        assert toml.exists()
        assert "[debug]" in toml.read_text()


class TestListConfig:
    def test_returns_flat_dict(self, tmp_path):
        toml = tmp_path / "edesto.toml"
        toml.write_text('[serial]\nport = "/dev/ttyUSB0"\nbaud_rate = 9600\n\n[debug]\ngpio = 25\n')
        result = list_config(tmp_path)
        assert result["serial.port"] == "/dev/ttyUSB0"
        assert result["serial.baud_rate"] == 9600
        assert result["debug.gpio"] == 25

    def test_empty_toml(self, tmp_path):
        toml = tmp_path / "edesto.toml"
        toml.write_text("")
        result = list_config(tmp_path)
        assert result == {}


class TestEnsureEdestoDir:
    def test_creates_dir_with_gitignore(self, tmp_path):
        result = ensure_edesto_dir(tmp_path)
        assert result.exists()
        assert result.is_dir()
        gitignore = result / ".gitignore"
        assert gitignore.exists()
        assert "*" in gitignore.read_text()

    def test_idempotent(self, tmp_path):
        ensure_edesto_dir(tmp_path)
        ensure_edesto_dir(tmp_path)
        assert (tmp_path / ".edesto").exists()


class TestScanCache:
    def test_roundtrip(self, tmp_path):
        ensure_edesto_dir(tmp_path)
        data = {"serial": {"boot_marker": "[READY]"}, "logging_api": {"primary": "Serial.println"}}
        save_scan_cache(tmp_path, data)
        loaded = load_scan_cache(tmp_path)
        assert loaded == data

    def test_missing_returns_none(self, tmp_path):
        ensure_edesto_dir(tmp_path)
        assert load_scan_cache(tmp_path) is None


class TestInstrumentManifest:
    def test_roundtrip(self, tmp_path):
        ensure_edesto_dir(tmp_path)
        data = {"entries": [{"file": "main.c", "line": 42}]}
        save_instrument_manifest(tmp_path, data)
        loaded = load_instrument_manifest(tmp_path)
        assert loaded == data

    def test_missing_returns_none(self, tmp_path):
        ensure_edesto_dir(tmp_path)
        assert load_instrument_manifest(tmp_path) is None


class TestDebugLog:
    def test_append_creates_file(self, tmp_path):
        ensure_edesto_dir(tmp_path)
        append_debug_log(tmp_path, {"message": "test"})
        log_path = tmp_path / ".edesto" / "debug-log.jsonl"
        assert log_path.exists()
        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 1
        assert json.loads(lines[0])["message"] == "test"

    def test_append_multiple(self, tmp_path):
        ensure_edesto_dir(tmp_path)
        for i in range(3):
            append_debug_log(tmp_path, {"i": i})
        log_path = tmp_path / ".edesto" / "debug-log.jsonl"
        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 3

    def test_truncation_at_10mb(self, tmp_path):
        ensure_edesto_dir(tmp_path)
        log_path = tmp_path / ".edesto" / "debug-log.jsonl"
        # Write slightly over 10MB
        big_entry = {"data": "x" * 1000}
        line = json.dumps(big_entry) + "\n"
        # Fill to ~10.1MB
        count = (10 * 1024 * 1024) // len(line) + 100
        log_path.write_text(line * count)
        assert log_path.stat().st_size > 10 * 1024 * 1024
        # Append should trigger truncation
        append_debug_log(tmp_path, {"message": "after truncation"})
        assert log_path.stat().st_size < 10 * 1024 * 1024


class TestClearDebugState:
    def test_clears_all_files(self, tmp_path):
        ensure_edesto_dir(tmp_path)
        edesto_dir = tmp_path / ".edesto"
        (edesto_dir / "debug-log.jsonl").write_text('{"a":1}\n')
        (edesto_dir / "instrument-manifest.json").write_text('{}')
        (edesto_dir / "debug-scan.json").write_text('{}')
        clear_debug_state(tmp_path)
        assert not (edesto_dir / "debug-log.jsonl").exists()
        assert not (edesto_dir / "instrument-manifest.json").exists()
        assert not (edesto_dir / "debug-scan.json").exists()

    def test_ok_when_no_files(self, tmp_path):
        ensure_edesto_dir(tmp_path)
        clear_debug_state(tmp_path)  # Should not raise
