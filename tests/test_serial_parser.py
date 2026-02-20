"""Tests for the serial line parser."""

import json

from edesto_dev.serial.parser import ParserConfig, ParsedLine, LineParser


class TestLineParserRaw:
    def test_raw_passthrough(self):
        parser = LineParser()
        result = parser.parse_line("hello world", "2024-01-01T00:00:00")
        assert result.raw == "hello world"
        assert result.ts == "2024-01-01T00:00:00"

    def test_empty_line(self):
        parser = LineParser()
        result = parser.parse_line("", "2024-01-01T00:00:00")
        assert result.raw == ""
        assert result.tag is None


class TestEdestoTaggedLine:
    def test_tagged_line(self):
        parser = LineParser(ParserConfig(known_tags=["SENSOR", "ERROR", "STATUS"]))
        result = parser.parse_line("[SENSOR] temp=23.4 humidity=65", "ts")
        assert result.tag == "SENSOR"
        assert result.data.get("temp") == "23.4"
        assert result.data.get("humidity") == "65"

    def test_error_tag(self):
        parser = LineParser(ParserConfig(known_tags=["ERROR"]))
        result = parser.parse_line("[ERROR] something went wrong", "ts")
        assert result.tag == "ERROR"
        assert "message" in result.data

    def test_unknown_tag_not_extracted(self):
        parser = LineParser(ParserConfig(known_tags=["SENSOR"]))
        result = parser.parse_line("[UNKNOWN] some data", "ts")
        # Unknown tag not extracted - treated as raw
        assert result.tag is None


class TestKeyValuePairs:
    def test_key_value_extraction(self):
        parser = LineParser()
        result = parser.parse_line("temp=23.4 humidity=65 status=ok", "ts")
        assert result.data.get("temp") == "23.4"
        assert result.data.get("humidity") == "65"
        assert result.data.get("status") == "ok"


class TestEspIdfLog:
    def test_esp_idf_format(self):
        parser = LineParser()
        result = parser.parse_line("I (123) wifi: Connected to AP", "ts")
        assert result.tag == "wifi"
        assert result.data.get("level") == "I"
        assert result.data.get("timestamp") == "123"
        assert "Connected to AP" in result.data.get("message", "")


class TestZephyrLog:
    def test_zephyr_format(self):
        parser = LineParser()
        result = parser.parse_line("[00:00:01.234,567] <inf> my_module: System ready", "ts")
        assert result.tag == "my_module"
        assert result.data.get("level") == "inf"
        assert "System ready" in result.data.get("message", "")


class TestAtResponse:
    def test_at_response(self):
        parser = LineParser()
        result = parser.parse_line("+CWJAP:connected", "ts")
        assert result.tag == "CWJAP"
        assert result.data.get("params") == "connected"


class TestJsonFragment:
    def test_json_fragment(self):
        parser = LineParser()
        json_str = '{"temp": 23.4, "status": "ok"}'
        result = parser.parse_line(json_str, "ts")
        assert result.data.get("temp") == 23.4
        assert result.data.get("status") == "ok"


class TestParserConfig:
    def test_from_scan_cache(self):
        cache = {
            "serial": {
                "boot_marker": "[READY]",
                "success_markers": ["[OK]", "[DONE]"],
                "error_markers": ["[ERROR]"],
                "echo": True,
                "prompt": "> ",
                "line_terminator": "\r\n",
            }
        }
        config = ParserConfig.from_scan_cache(cache)
        assert config.boot_marker == "[READY]"
        assert config.success_markers == ["[OK]", "[DONE]"]
        assert config.echo is True
        assert config.prompt == "> "

    def test_custom_config(self):
        config = ParserConfig(
            known_tags=["DATA", "LOG"],
            boot_marker="BOOT_OK",
        )
        parser = LineParser(config)
        result = parser.parse_line("[DATA] value=42", "ts")
        assert result.tag == "DATA"
        assert result.data.get("value") == "42"


class TestParsedLine:
    def test_to_dict(self):
        line = ParsedLine(ts="ts", raw="hello", tag="TAG", data={"key": "val"})
        d = line.to_dict()
        assert d["ts"] == "ts"
        assert d["raw"] == "hello"
        assert d["tag"] == "TAG"
        assert d["data"]["key"] == "val"
