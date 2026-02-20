"""Tests for the debug scan engine."""

import json
from pathlib import Path

import pytest

from edesto_dev.debug.scan import scan_project, ScanResult


def _write_source(tmp_path, filename, content):
    """Helper to write a source file."""
    filepath = tmp_path / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content)
    return filepath


class TestDetectArduinoLogging:
    def test_serial_println(self, tmp_path):
        _write_source(tmp_path, "main.ino", '''
void setup() {
    Serial.begin(115200);
    Serial.println("[READY]");
    Serial.println("[SENSOR] temp=23.4");
}
void loop() {
    Serial.println("hello");
}
''')
        result = scan_project(tmp_path)
        assert result.logging_api["primary"] == "Serial.println"

    def test_serial_printf(self, tmp_path):
        _write_source(tmp_path, "main.ino", '''
void setup() {
    Serial.begin(115200);
    Serial.printf("value=%d\\n", val);
    Serial.printf("other=%d\\n", other);
}
''')
        result = scan_project(tmp_path)
        assert "Serial" in result.logging_api["primary"]


class TestDetectEspIdfLogging:
    def test_esp_logi(self, tmp_path):
        _write_source(tmp_path, "main.c", '''
#include "esp_log.h"
static const char *TAG = "main";
void app_main() {
    ESP_LOGI(TAG, "Starting up");
    ESP_LOGI(TAG, "Ready");
    ESP_LOGW(TAG, "Warning");
}
''')
        result = scan_project(tmp_path)
        assert "ESP_LOG" in result.logging_api["primary"]


class TestDetectZephyrLogging:
    def test_log_inf(self, tmp_path):
        _write_source(tmp_path, "main.c", '''
#include <zephyr/logging/log.h>
LOG_MODULE_REGISTER(my_app, LOG_LEVEL_INF);
void main() {
    LOG_INF("System started");
    LOG_INF("Ready");
    LOG_ERR("Error occurred");
}
''')
        result = scan_project(tmp_path)
        assert "LOG_INF" in result.logging_api["primary"] or "LOG_" in result.logging_api["primary"]


class TestDetectPrintf:
    def test_printf(self, tmp_path):
        _write_source(tmp_path, "main.c", '''
#include <stdio.h>
int main() {
    printf("Hello world\\n");
    printf("value=%d\\n", val);
    printf("done\\n");
}
''')
        result = scan_project(tmp_path)
        assert result.logging_api["primary"] == "printf"


class TestSerialProperties:
    def test_extract_boot_marker(self, tmp_path):
        _write_source(tmp_path, "main.ino", '''
void setup() {
    Serial.begin(115200);
    Serial.println("[READY]");
}
void loop() {}
''')
        result = scan_project(tmp_path)
        assert result.serial["boot_marker"] == "[READY]"

    def test_extract_error_markers(self, tmp_path):
        _write_source(tmp_path, "main.ino", '''
void setup() {
    Serial.begin(115200);
    Serial.println("[READY]");
}
void handleError() {
    Serial.println("[ERROR] something failed");
}
void loop() {
    Serial.println("[DONE]");
}
''')
        result = scan_project(tmp_path)
        assert "[ERROR]" in result.serial.get("error_markers", [])


class TestDetectBaudRate:
    def test_serial_begin(self, tmp_path):
        _write_source(tmp_path, "main.ino", '''
void setup() {
    Serial.begin(9600);
}
''')
        result = scan_project(tmp_path)
        assert result.serial.get("baud_rate") == 9600

    def test_serial_begin_115200(self, tmp_path):
        _write_source(tmp_path, "main.ino", '''
void setup() {
    Serial.begin(115200);
}
''')
        result = scan_project(tmp_path)
        assert result.serial.get("baud_rate") == 115200


class TestDetectDangerZones:
    def test_isr_function(self, tmp_path):
        _write_source(tmp_path, "main.c", '''
void IRAM_ATTR button_isr() {
    // handle interrupt
    gpio_set_level(LED_PIN, 1);
}
void app_main() {
    // safe zone
}
''')
        result = scan_project(tmp_path)
        assert len(result.danger_zones) > 0
        names = [dz.get("function", "") for dz in result.danger_zones]
        assert any("button_isr" in n for n in names)

    def test_iram_attr(self, tmp_path):
        _write_source(tmp_path, "main.c", '''
void IRAM_ATTR timer_handler(void *arg) {
    count++;
}
''')
        result = scan_project(tmp_path)
        assert len(result.danger_zones) > 0


class TestDetectSafeZones:
    def test_setup_function(self, tmp_path):
        _write_source(tmp_path, "main.ino", '''
void setup() {
    Serial.begin(115200);
}
void loop() {
    delay(1000);
}
''')
        result = scan_project(tmp_path)
        assert len(result.safe_zones) > 0
        names = [sz.get("function", "") for sz in result.safe_zones]
        assert any("setup" in n for n in names)

    def test_app_main(self, tmp_path):
        _write_source(tmp_path, "main.c", '''
void app_main() {
    printf("Starting\\n");
}
''')
        result = scan_project(tmp_path)
        names = [sz.get("function", "") for sz in result.safe_zones]
        assert any("app_main" in n for n in names)


class TestSkipDirs:
    def test_skip_build_dir(self, tmp_path):
        _write_source(tmp_path, "src/main.c", 'void app_main() { printf("hello\\n"); }')
        _write_source(tmp_path, "build/generated.c", 'void generated() { printf("nope\\n"); }')
        result = scan_project(tmp_path)
        # Should not include files from build/
        files = set()
        for zone in result.safe_zones + result.danger_zones:
            files.add(zone.get("file", ""))
        assert not any("build" in f for f in files)

    def test_skip_pio_dir(self, tmp_path):
        _write_source(tmp_path, "src/main.c", 'void app_main() { printf("hello\\n"); }')
        _write_source(tmp_path, ".pio/build/main.c", 'void generated() {}')
        result = scan_project(tmp_path)
        files = set()
        for zone in result.safe_zones + result.danger_zones:
            files.add(zone.get("file", ""))
        assert not any(".pio" in f for f in files)


class TestEmptyProject:
    def test_scan_empty(self, tmp_path):
        result = scan_project(tmp_path)
        assert result.logging_api["primary"] is None
        assert result.serial["boot_marker"] is None
        assert result.danger_zones == []
        assert result.safe_zones == []


class TestScanResultRoundtrip:
    def test_to_dict_from_dict(self, tmp_path):
        _write_source(tmp_path, "main.ino", '''
void setup() {
    Serial.begin(115200);
    Serial.println("[READY]");
}
void loop() {}
''')
        result = scan_project(tmp_path)
        d = result.to_dict()
        # Verify serializable
        json_str = json.dumps(d)
        loaded = json.loads(json_str)
        result2 = ScanResult.from_dict(loaded)
        assert result2.serial["boot_marker"] == result.serial["boot_marker"]
        assert result2.logging_api["primary"] == result.logging_api["primary"]


class TestCommandDetection:
    def test_strcmp_chain(self, tmp_path):
        _write_source(tmp_path, "commands.c", '''
void handle_command(const char *cmd) {
    if (strcmp(cmd, "read_sensor") == 0) {
        read_sensor();
    } else if (strcmp(cmd, "set_led") == 0) {
        set_led(atoi(cmd + 8));
    } else if (strcmp(cmd, "reset") == 0) {
        reset_device();
    }
}
''')
        result = scan_project(tmp_path)
        commands = [c["command"] for c in result.serial.get("known_commands", [])]
        assert "read_sensor" in commands
        assert "set_led" in commands
        assert "reset" in commands


class TestScanSpecificPath:
    def test_scan_path(self, tmp_path):
        _write_source(tmp_path, "src/main.c", 'void app_main() { printf("hello\\n"); }')
        _write_source(tmp_path, "lib/util.c", 'void helper() { printf("help\\n"); }')
        result = scan_project(tmp_path, path=tmp_path / "src")
        safe_files = [sz.get("file", "") for sz in result.safe_zones]
        assert any("main.c" in f for f in safe_files)
        # Should not include lib files when path is restricted
        assert not any("util.c" in f for f in safe_files)
