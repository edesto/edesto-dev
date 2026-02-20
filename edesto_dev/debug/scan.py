"""Regex-based static analysis of C/C++/ino source files for debug scanning."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_SKIP_DIRS = {"build", ".pio", ".git", "node_modules", ".edesto"}
_SOURCE_EXTENSIONS = {".c", ".cpp", ".h", ".hpp", ".ino"}

# Logging API patterns
_SERIAL_PRINT_RE = re.compile(r"\bSerial\.(println|printf|print|write)\b")
_ESP_LOG_RE = re.compile(r"\bESP_LOG[IWEDV]\b")
_ZEPHYR_LOG_RE = re.compile(r"\bLOG_(INF|WRN|ERR|DBG)\b")
_PRINTF_RE = re.compile(r"\bprintf\s*\(")
_PRINTK_RE = re.compile(r"\bprintk\s*\(")

# Baud rate
_SERIAL_BEGIN_RE = re.compile(r"\bSerial\.begin\s*\(\s*(\d+)\s*\)")
_UART_CONFIG_BAUD_RE = re.compile(r"\.baud_rate\s*=\s*(\d+)")

# Markers - strings in print/log calls containing [TAG] patterns
_MARKER_RE = re.compile(r'(?:println|printf|print|ESP_LOG[IWEDV]|LOG_(?:INF|WRN|ERR))\s*\([^)]*"([^"]*\[[A-Z_]+\][^"]*)"')
_BRACKET_TAG_RE = re.compile(r"\[([A-Z_]+)\]")

# Command detection
_STRCMP_RE = re.compile(r'strcmp\s*\(\s*\w+\s*,\s*"([^"]+)"\s*\)\s*==\s*0')

# Danger zones
_ISR_FUNC_RE = re.compile(r"\b(?:void\s+)?((?:IRAM_ATTR\s+)?(?:\w*(?:ISR|IRQ|Handler|isr_|_irq|interrupt)\w*))\s*\(")
_IRAM_ATTR_RE = re.compile(r"\bIRAM_ATTR\b")
_INTERRUPT_ATTR_RE = re.compile(r'__attribute__\s*\(\s*\(\s*interrupt\s*\)\s*\)')
_NO_INTERRUPTS_RE = re.compile(r"\b(?:noInterrupts|cli|__disable_irq)\s*\(")

# Safe zones
_SAFE_FUNC_RE = re.compile(r"\b(?:void\s+)?(setup|main|app_main|loop)\s*\(")


@dataclass
class ScanResult:
    serial: dict = field(default_factory=lambda: {
        "line_terminator": "\n",
        "boot_marker": None,
        "success_markers": [],
        "error_markers": [],
        "echo": False,
        "prompt": None,
        "known_commands": [],
        "baud_rate": None,
    })
    logging_api: dict = field(default_factory=lambda: {
        "primary": None,
        "variants": [],
        "tag_convention": None,
        "examples": [],
    })
    danger_zones: list[dict] = field(default_factory=list)
    safe_zones: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "serial": self.serial,
            "logging_api": self.logging_api,
            "danger_zones": self.danger_zones,
            "safe_zones": self.safe_zones,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ScanResult:
        return cls(
            serial=data.get("serial", {}),
            logging_api=data.get("logging_api", {}),
            danger_zones=data.get("danger_zones", []),
            safe_zones=data.get("safe_zones", []),
        )


def scan_project(project_dir: Path | str, path: Path | str | None = None) -> ScanResult:
    """Scan source files for debug-relevant patterns."""
    project_dir = Path(project_dir)
    scan_dir = Path(path) if path else project_dir

    result = ScanResult()
    api_counts: dict[str, int] = {}
    api_variants: list[str] = []
    all_markers: list[str] = []
    all_commands: list[dict] = []
    baud_rate = None

    for filepath in _iter_source_files(scan_dir, project_dir):
        content = filepath.read_text(errors="ignore")
        rel_path = str(filepath.relative_to(project_dir))

        # Detect logging APIs
        _count_logging_apis(content, api_counts, api_variants)

        # Detect serial properties
        markers = _detect_markers(content)
        all_markers.extend(markers)

        # Detect baud rate
        br = _detect_baud_rate(content)
        if br is not None:
            baud_rate = br

        # Detect commands
        cmds = _detect_commands(content, rel_path)
        all_commands.extend(cmds)

        # Detect danger zones
        dangers = _detect_danger_zones(content, rel_path)
        result.danger_zones.extend(dangers)

        # Detect safe zones
        safes = _detect_safe_zones(content, rel_path)
        result.safe_zones.extend(safes)

        # Detect tag convention
        tag_match = re.search(r'static\s+const\s+char\s*\*\s*TAG\s*=\s*"([^"]+)"', content)
        if tag_match and result.logging_api["tag_convention"] is None:
            result.logging_api["tag_convention"] = tag_match.group(0)

    # Determine primary logging API
    if api_counts:
        primary = max(api_counts, key=api_counts.get)
        result.logging_api["primary"] = primary
        result.logging_api["variants"] = sorted(set(api_variants))

    # Process markers
    boot_marker = None
    success_markers = []
    error_markers = []
    for marker_str in all_markers:
        tags = _BRACKET_TAG_RE.findall(marker_str)
        for tag in tags:
            full = f"[{tag}]"
            if tag == "READY":
                boot_marker = full
            elif tag in ("ERROR",):
                if full not in error_markers:
                    error_markers.append(full)
            elif tag in ("OK", "DONE"):
                if full not in success_markers:
                    success_markers.append(full)

    result.serial["boot_marker"] = boot_marker
    result.serial["success_markers"] = success_markers
    result.serial["error_markers"] = error_markers
    result.serial["known_commands"] = all_commands
    result.serial["baud_rate"] = baud_rate

    return result


def _iter_source_files(scan_dir: Path, project_dir: Path):
    """Iterate source files, skipping build directories."""
    for filepath in scan_dir.rglob("*"):
        if not filepath.is_file():
            continue
        if filepath.suffix not in _SOURCE_EXTENSIONS:
            continue
        # Check if any parent dir is in skip list
        try:
            rel = filepath.relative_to(project_dir)
        except ValueError:
            rel = filepath
        if any(part in _SKIP_DIRS for part in rel.parts):
            continue
        yield filepath


def _count_logging_apis(content: str, counts: dict, variants: list):
    """Count occurrences of each logging API family."""
    serial_count = len(_SERIAL_PRINT_RE.findall(content))
    if serial_count:
        # Determine the most specific variant
        println_count = content.count("Serial.println")
        printf_count = content.count("Serial.printf")
        if printf_count > println_count:
            key = "Serial.printf"
        else:
            key = "Serial.println"
        counts[key] = counts.get(key, 0) + serial_count
        if "Serial.println" not in variants:
            variants.append("Serial.println")
        if "Serial.printf" not in variants and printf_count > 0:
            variants.append("Serial.printf")

    esp_count = len(_ESP_LOG_RE.findall(content))
    if esp_count:
        counts["ESP_LOG"] = counts.get("ESP_LOG", 0) + esp_count
        for var in _ESP_LOG_RE.findall(content):
            full = f"ESP_LOG{var}"
            if full not in variants:
                variants.append(full)

    zephyr_count = len(_ZEPHYR_LOG_RE.findall(content))
    if zephyr_count:
        counts["LOG_INF"] = counts.get("LOG_INF", 0) + zephyr_count
        for var in _ZEPHYR_LOG_RE.findall(content):
            full = f"LOG_{var}"
            if full not in variants:
                variants.append(full)

    printf_count = len(_PRINTF_RE.findall(content))
    if printf_count:
        counts["printf"] = counts.get("printf", 0) + printf_count
        if "printf" not in variants:
            variants.append("printf")

    printk_count = len(_PRINTK_RE.findall(content))
    if printk_count:
        counts["printk"] = counts.get("printk", 0) + printk_count
        if "printk" not in variants:
            variants.append("printk")


def _detect_markers(content: str) -> list[str]:
    """Extract string literals containing [TAG] patterns from print/log calls."""
    return _MARKER_RE.findall(content)


def _detect_baud_rate(content: str) -> int | None:
    """Detect baud rate from Serial.begin() or uart config."""
    m = _SERIAL_BEGIN_RE.search(content)
    if m:
        return int(m.group(1))
    m = _UART_CONFIG_BAUD_RE.search(content)
    if m:
        return int(m.group(1))
    return None


def _detect_commands(content: str, filename: str) -> list[dict]:
    """Detect command strings from strcmp chains."""
    commands = []
    for i, line in enumerate(content.splitlines(), 1):
        for m in _STRCMP_RE.finditer(line):
            commands.append({
                "command": m.group(1),
                "args": None,
                "file": filename,
                "line": i,
            })
    return commands


def _detect_danger_zones(content: str, filename: str) -> list[dict]:
    """Detect ISR functions and other danger zones."""
    zones = []
    lines = content.splitlines()

    for i, line in enumerate(lines, 1):
        # IRAM_ATTR functions
        if _IRAM_ATTR_RE.search(line):
            func_match = re.search(r"\b(\w+)\s*\(", line)
            if func_match:
                # Skip "IRAM_ATTR" itself as func name
                name = func_match.group(1)
                if name != "IRAM_ATTR":
                    zones.append({
                        "file": filename,
                        "function": name,
                        "line_range": [i, i],
                        "reason": "IRAM_ATTR (ISR context)",
                    })
                    continue

        # ISR function names
        m = _ISR_FUNC_RE.search(line)
        if m and "IRAM_ATTR" not in line:
            name = m.group(1).replace("IRAM_ATTR ", "")
            zones.append({
                "file": filename,
                "function": name,
                "line_range": [i, i],
                "reason": "ISR function",
            })
            continue

        # __attribute__((interrupt))
        if _INTERRUPT_ATTR_RE.search(line):
            func_match = re.search(r"\b(\w+)\s*\(", line)
            if func_match:
                zones.append({
                    "file": filename,
                    "function": func_match.group(1),
                    "line_range": [i, i],
                    "reason": "interrupt attribute",
                })

    return zones


def _detect_safe_zones(content: str, filename: str) -> list[dict]:
    """Detect setup(), main(), app_main(), loop() functions."""
    zones = []
    for i, line in enumerate(content.splitlines(), 1):
        m = _SAFE_FUNC_RE.search(line)
        if m:
            zones.append({
                "file": filename,
                "function": m.group(1),
                "line_range": [i, i],
            })
    return zones
