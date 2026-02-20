"""Tests for the debug instrumentation engine."""

import json
from pathlib import Path

import pytest

from edesto_dev.debug.instrument import (
    instrument_line,
    instrument_function,
    instrument_gpio,
    clean_all,
    InstrumentManifest,
    CleanResult,
)


def _write_source(tmp_path, filename, content):
    filepath = tmp_path / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content)
    return filepath


class TestInstrumentLineArduino:
    def test_insert_arduino_print(self, tmp_path):
        src = _write_source(tmp_path, "main.ino", '''void setup() {
    Serial.begin(115200);
    int val = 42;
    Serial.println(val);
}
''')
        manifest = InstrumentManifest()
        instrument_line(src, 3, exprs=["val"], logging_api="Serial.println", manifest=manifest)
        content = src.read_text()
        assert "EDESTO_TEMP_DEBUG" in content
        assert "val" in content
        assert len(manifest.entries) == 1

    def test_arduino_no_fmt_needed(self, tmp_path):
        src = _write_source(tmp_path, "main.ino", '''void setup() {
    int val = 42;
}
''')
        manifest = InstrumentManifest()
        # Should not raise ValueError for Arduino (String concat)
        instrument_line(src, 2, exprs=["val"], logging_api="Serial.println", manifest=manifest)
        content = src.read_text()
        assert "EDESTO_TEMP_DEBUG" in content


class TestInstrumentLineEspIdf:
    def test_insert_esp_log(self, tmp_path):
        src = _write_source(tmp_path, "main.c", '''void app_main() {
    int val = 42;
    printf("done\\n");
}
''')
        manifest = InstrumentManifest()
        instrument_line(src, 2, exprs=["val"], fmts=["%d"], logging_api="ESP_LOGI", manifest=manifest)
        content = src.read_text()
        assert "EDESTO_TEMP_DEBUG" in content
        assert "ESP_LOGI" in content


class TestInstrumentLinePrintf:
    def test_printf_requires_fmt(self, tmp_path):
        src = _write_source(tmp_path, "main.c", '''int main() {
    int val = 42;
}
''')
        manifest = InstrumentManifest()
        with pytest.raises(ValueError, match="fmt"):
            instrument_line(src, 2, exprs=["val"], logging_api="printf", manifest=manifest)

    def test_printf_with_fmt(self, tmp_path):
        src = _write_source(tmp_path, "main.c", '''int main() {
    int val = 42;
}
''')
        manifest = InstrumentManifest()
        instrument_line(src, 2, exprs=["val"], fmts=["%d"], logging_api="printf", manifest=manifest)
        content = src.read_text()
        assert "EDESTO_TEMP_DEBUG" in content
        assert "printf" in content


class TestInstrumentLineZephyr:
    def test_zephyr_requires_fmt(self, tmp_path):
        src = _write_source(tmp_path, "main.c", '''void main() {
    int val = 42;
}
''')
        manifest = InstrumentManifest()
        with pytest.raises(ValueError, match="fmt"):
            instrument_line(src, 2, exprs=["val"], logging_api="LOG_INF", manifest=manifest)


class TestInstrumentFunction:
    def test_function_entry_exit(self, tmp_path):
        src = _write_source(tmp_path, "main.c", '''void my_func(int x) {
    int y = x * 2;
    return;
}
''')
        manifest = InstrumentManifest()
        instrument_function(src, "my_func", logging_api="printf", manifest=manifest)
        content = src.read_text()
        assert ">>> my_func" in content
        assert "<<< my_func" in content
        assert "EDESTO_TEMP_DEBUG" in content

    def test_function_with_multiple_returns(self, tmp_path):
        src = _write_source(tmp_path, "main.c", '''int compute(int x) {
    if (x < 0) {
        return -1;
    }
    return x * 2;
}
''')
        manifest = InstrumentManifest()
        instrument_function(src, "compute", logging_api="printf", manifest=manifest)
        content = src.read_text()
        assert content.count("<<< compute") == 2  # Before each return


class TestInstrumentGpio:
    def test_gpio_toggle(self, tmp_path):
        src = _write_source(tmp_path, "main.c", '''void process() {
    int val = compute();
    send(val);
}
''')
        manifest = InstrumentManifest()
        instrument_gpio(src, 2, gpio_pin=25, manifest=manifest)
        content = src.read_text()
        assert "digitalWrite(25, HIGH)" in content
        assert "digitalWrite(25, LOW)" in content
        assert "EDESTO_TEMP_DEBUG" in content

    def test_gpio_without_config_errors(self, tmp_path):
        src = _write_source(tmp_path, "main.c", '''void process() {
    int val = compute();
}
''')
        manifest = InstrumentManifest()
        with pytest.raises(ValueError, match="gpio"):
            instrument_gpio(src, 2, gpio_pin=None, manifest=manifest)


class TestClean:
    def test_clean_removes_all_markers(self, tmp_path):
        src = _write_source(tmp_path, "main.c", '''void setup() {
    Serial.println("EDESTO_DEBUG val=" + String(val)); // EDESTO_TEMP_DEBUG
    int val = 42;
    Serial.println("EDESTO_DEBUG other=" + String(other)); // EDESTO_TEMP_DEBUG
}
''')
        result = clean_all(tmp_path)
        content = src.read_text()
        assert "EDESTO_TEMP_DEBUG" not in content
        assert result.removed_count == 2

    def test_clean_dry_run(self, tmp_path):
        src = _write_source(tmp_path, "main.c", '''void setup() {
    printf("EDESTO_DEBUG val=%d\\n", val); // EDESTO_TEMP_DEBUG
    int val = 42;
}
''')
        result = clean_all(tmp_path, dry_run=True)
        content = src.read_text()
        assert "EDESTO_TEMP_DEBUG" in content  # Not removed
        assert result.removed_count == 1  # But reported

    def test_clean_specific_file(self, tmp_path):
        src1 = _write_source(tmp_path, "a.c", '''int x; // EDESTO_TEMP_DEBUG\n''')
        src2 = _write_source(tmp_path, "b.c", '''int y; // EDESTO_TEMP_DEBUG\n''')
        result = clean_all(tmp_path, file=src1)
        assert "EDESTO_TEMP_DEBUG" not in src1.read_text()
        assert "EDESTO_TEMP_DEBUG" in src2.read_text()
        assert result.removed_count == 1

    def test_clean_no_markers(self, tmp_path):
        _write_source(tmp_path, "main.c", '''void setup() {
    int val = 42;
}
''')
        result = clean_all(tmp_path)
        assert result.removed_count == 0


class TestDangerZoneRefusal:
    def test_refuses_in_danger_zone(self, tmp_path):
        src = _write_source(tmp_path, "main.c", '''void IRAM_ATTR my_isr() {
    gpio_set_level(LED_PIN, 1);
}
''')
        # Create scan cache with danger zone
        edesto_dir = tmp_path / ".edesto"
        edesto_dir.mkdir(exist_ok=True)
        (edesto_dir / ".gitignore").write_text("*\n")
        scan_data = {
            "serial": {"boot_marker": None, "success_markers": [], "error_markers": [],
                       "echo": False, "prompt": None, "line_terminator": "\n", "known_commands": [], "baud_rate": None},
            "logging_api": {"primary": "printf", "variants": [], "tag_convention": None, "examples": []},
            "danger_zones": [{"file": "main.c", "function": "my_isr", "line_range": [1, 3], "reason": "IRAM_ATTR"}],
            "safe_zones": [],
        }
        (edesto_dir / "debug-scan.json").write_text(json.dumps(scan_data))
        manifest = InstrumentManifest()
        with pytest.raises(ValueError, match="danger zone"):
            instrument_line(src, 2, exprs=["LED_PIN"], fmts=["%d"], logging_api="printf",
                          manifest=manifest, project_dir=tmp_path)

    def test_force_overrides_danger_zone(self, tmp_path):
        src = _write_source(tmp_path, "main.c", '''void IRAM_ATTR my_isr() {
    gpio_set_level(LED_PIN, 1);
}
''')
        edesto_dir = tmp_path / ".edesto"
        edesto_dir.mkdir(exist_ok=True)
        (edesto_dir / ".gitignore").write_text("*\n")
        scan_data = {
            "serial": {"boot_marker": None, "success_markers": [], "error_markers": [],
                       "echo": False, "prompt": None, "line_terminator": "\n", "known_commands": [], "baud_rate": None},
            "logging_api": {"primary": "printf", "variants": [], "tag_convention": None, "examples": []},
            "danger_zones": [{"file": "main.c", "function": "my_isr", "line_range": [1, 3], "reason": "IRAM_ATTR"}],
            "safe_zones": [],
        }
        (edesto_dir / "debug-scan.json").write_text(json.dumps(scan_data))
        manifest = InstrumentManifest()
        instrument_line(src, 2, exprs=["LED_PIN"], fmts=["%d"], logging_api="printf",
                       manifest=manifest, project_dir=tmp_path, force=True)
        content = src.read_text()
        assert "EDESTO_TEMP_DEBUG" in content


class TestManifest:
    def test_roundtrip(self):
        manifest = InstrumentManifest()
        manifest.entries.append({"file": "main.c", "line": 42, "content": "debug"})
        d = manifest.to_dict()
        loaded = InstrumentManifest.from_dict(d)
        assert len(loaded.entries) == 1
        assert loaded.entries[0]["file"] == "main.c"


class TestCleanResult:
    def test_attributes(self):
        result = CleanResult(removed_count=3, removed_lines=["a", "b", "c"], orphan_warnings=[])
        assert result.removed_count == 3
        assert len(result.removed_lines) == 3
