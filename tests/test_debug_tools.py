"""Tests for debug tool detection."""

from unittest.mock import patch

from edesto_dev.debug_tools import detect_debug_tools


class TestDetectDebugTools:
    def test_returns_list(self):
        result = detect_debug_tools()
        assert isinstance(result, list)

    @patch("edesto_dev.debug_tools.shutil.which", return_value="/usr/bin/openocd")
    @patch("edesto_dev.debug_tools._check_import", side_effect=lambda name: name == "saleae")
    def test_detects_openocd_and_saleae(self, mock_import, mock_which):
        result = detect_debug_tools()
        assert "openocd" in result
        assert "saleae" in result

    @patch("edesto_dev.debug_tools.shutil.which", return_value=None)
    @patch("edesto_dev.debug_tools._check_import", return_value=False)
    def test_empty_when_nothing_installed(self, mock_import, mock_which):
        result = detect_debug_tools()
        assert result == []

    @patch("edesto_dev.debug_tools.shutil.which", return_value=None)
    @patch("edesto_dev.debug_tools._check_import", side_effect=lambda name: name == "pyvisa")
    def test_detects_scope_only(self, mock_import, mock_which):
        result = detect_debug_tools()
        assert result == ["scope"]
