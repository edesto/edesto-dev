"""Stateless per-line serial output parser for edesto-dev."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field


@dataclass
class ParserConfig:
    boot_marker: str | None = None
    success_markers: list[str] = field(default_factory=list)
    error_markers: list[str] = field(default_factory=list)
    echo: bool = False
    prompt: str | None = None
    line_terminator: str = "\n"
    known_tags: list[str] = field(default_factory=list)

    @classmethod
    def from_scan_cache(cls, data: dict) -> ParserConfig:
        serial = data.get("serial", {})
        # Build known_tags from markers
        known_tags = []
        for marker in (
            serial.get("success_markers", [])
            + serial.get("error_markers", [])
            + ([serial["boot_marker"]] if serial.get("boot_marker") else [])
        ):
            # Extract tag from [TAG] format
            m = re.match(r"\[([A-Z_]+)\]", marker)
            if m:
                tag = m.group(1)
                if tag not in known_tags:
                    known_tags.append(tag)
        return cls(
            boot_marker=serial.get("boot_marker"),
            success_markers=serial.get("success_markers", []),
            error_markers=serial.get("error_markers", []),
            echo=serial.get("echo", False),
            prompt=serial.get("prompt"),
            line_terminator=serial.get("line_terminator", "\n"),
            known_tags=known_tags,
        )


@dataclass
class ParsedLine:
    ts: str
    raw: str
    tag: str | None = None
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "ts": self.ts,
            "raw": self.raw,
            "tag": self.tag,
            "data": self.data,
        }


# ESP-IDF log: I (123) tag: message
_ESP_IDF_RE = re.compile(r"^([IWEDV])\s+\((\d+)\)\s+(\S+?):\s*(.*)$")

# Zephyr log: [00:00:01.234,567] <inf> module: message
_ZEPHYR_RE = re.compile(r"^\[[\d:.,]+\]\s+<(\w+)>\s+(\S+?):\s*(.*)$")

# AT command response: +COMMAND:params
_AT_RE = re.compile(r"^\+([A-Z0-9_]+):(.*)$")

# edesto tagged line: [TAG] payload
_TAGGED_RE = re.compile(r"^\[([A-Z_]+)\]\s*(.*)$")

# key=value pairs: key=value (space-separated)
_KV_RE = re.compile(r"(\w+)=([\S]+)")


class LineParser:
    """Parse a single line of serial output."""

    def __init__(self, config: ParserConfig | None = None):
        self.config = config

    def parse_line(self, raw: str, timestamp: str) -> ParsedLine:
        raw = raw.strip()
        if not raw:
            return ParsedLine(ts=timestamp, raw=raw, tag=None, data={})

        # 1. Known tags: [TAG] payload
        if self.config and self.config.known_tags:
            m = _TAGGED_RE.match(raw)
            if m and m.group(1) in self.config.known_tags:
                tag = m.group(1)
                payload = m.group(2)
                data = self._extract_kv(payload)
                if not data:
                    data = {"message": payload}
                return ParsedLine(ts=timestamp, raw=raw, tag=tag, data=data)

        # 2. Try key=value pairs (at least 2 pairs for this to be primary)
        kv_pairs = _KV_RE.findall(raw)
        if len(kv_pairs) >= 2:
            data = {k: v for k, v in kv_pairs}
            return ParsedLine(ts=timestamp, raw=raw, tag=None, data=data)

        # 3. ESP-IDF log format
        m = _ESP_IDF_RE.match(raw)
        if m:
            return ParsedLine(
                ts=timestamp, raw=raw,
                tag=m.group(3),
                data={"level": m.group(1), "timestamp": m.group(2), "message": m.group(4)},
            )

        # 4. Zephyr log format
        m = _ZEPHYR_RE.match(raw)
        if m:
            return ParsedLine(
                ts=timestamp, raw=raw,
                tag=m.group(2),
                data={"level": m.group(1), "message": m.group(3)},
            )

        # 5. AT-command response
        m = _AT_RE.match(raw)
        if m:
            return ParsedLine(
                ts=timestamp, raw=raw,
                tag=m.group(1),
                data={"params": m.group(2)},
            )

        # 6. JSON fragment
        if raw.startswith("{") and raw.endswith("}"):
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    return ParsedLine(ts=timestamp, raw=raw, tag=None, data=data)
            except (json.JSONDecodeError, ValueError):
                pass

        # 7. Fallback: raw line
        return ParsedLine(ts=timestamp, raw=raw, tag=None, data={"message": raw})

    def _extract_kv(self, text: str) -> dict:
        """Extract key=value pairs from text."""
        pairs = _KV_RE.findall(text)
        if pairs:
            return {k: v for k, v in pairs}
        return {}
