"""Tests for example projects."""

import ast
from pathlib import Path

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


class TestSensorDebugExample:
    def test_ino_file_exists(self):
        assert (EXAMPLES_DIR / "sensor-debug" / "sensor-debug.ino").exists()

    def test_claude_md_exists(self):
        assert (EXAMPLES_DIR / "sensor-debug" / "CLAUDE.md").exists()

    def test_validate_py_exists(self):
        assert (EXAMPLES_DIR / "sensor-debug" / "validate.py").exists()

    def test_validate_py_is_valid_python(self):
        source = (EXAMPLES_DIR / "sensor-debug" / "validate.py").read_text()
        ast.parse(source)

    def test_ino_has_bug(self):
        """The example intentionally has + 23 instead of + 32."""
        source = (EXAMPLES_DIR / "sensor-debug" / "sensor-debug.ino").read_text()
        assert "+ 23" in source
        assert "+ 32" not in source


class TestWifiEndpointExample:
    def test_ino_file_exists(self):
        assert (EXAMPLES_DIR / "wifi-endpoint" / "wifi-endpoint.ino").exists()

    def test_claude_md_exists(self):
        assert (EXAMPLES_DIR / "wifi-endpoint" / "CLAUDE.md").exists()

    def test_validate_py_exists(self):
        assert (EXAMPLES_DIR / "wifi-endpoint" / "validate.py").exists()

    def test_validate_py_is_valid_python(self):
        source = (EXAMPLES_DIR / "wifi-endpoint" / "validate.py").read_text()
        ast.parse(source)

    def test_config_example_exists(self):
        assert (EXAMPLES_DIR / "wifi-endpoint" / "config.h.example").exists()

    def test_ino_has_content_type_bug(self):
        """The example intentionally uses text/plain instead of application/json."""
        source = (EXAMPLES_DIR / "wifi-endpoint" / "wifi-endpoint.ino").read_text()
        assert '"text/plain"' in source
        assert '"application/json"' not in source


class TestOtaUpdateExample:
    def test_ino_file_exists(self):
        assert (EXAMPLES_DIR / "ota-update" / "ota-update.ino").exists()

    def test_claude_md_exists(self):
        assert (EXAMPLES_DIR / "ota-update" / "CLAUDE.md").exists()

    def test_validate_py_exists(self):
        assert (EXAMPLES_DIR / "ota-update" / "validate.py").exists()

    def test_validate_py_is_valid_python(self):
        source = (EXAMPLES_DIR / "ota-update" / "validate.py").read_text()
        ast.parse(source)

    def test_ino_has_version(self):
        source = (EXAMPLES_DIR / "ota-update" / "ota-update.ino").read_text()
        assert '"1.0.0"' in source
