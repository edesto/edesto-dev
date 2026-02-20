"""Debug status assembly for edesto-dev."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from edesto_dev.config import (
    load_scan_cache,
    load_instrument_manifest,
)


@dataclass
class DebugStatus:
    serial_log: dict = field(default_factory=dict)
    serial: dict | None = None
    project: dict = field(default_factory=dict)
    instrumentation: dict = field(default_factory=dict)
    tools: dict = field(default_factory=dict)
    device: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "serial_log": self.serial_log,
            "serial": self.serial,
            "project": self.project,
            "instrumentation": self.instrumentation,
            "tools": self.tools,
            "device": self.device,
        }

    def to_human(self) -> str:
        lines = ["Debug Status", "=" * 40, ""]

        # Serial Log
        lines.append("Serial Log:")
        sl = self.serial_log
        lines.append(f"  Total lines: {sl.get('total_lines', 0)}")
        lines.append(f"  Resets detected: {sl.get('resets_detected', 0)}")
        if sl.get("errors"):
            lines.append(f"  Errors: {len(sl['errors'])}")
            for err in sl["errors"]:
                lines.append(f"    {err['message']} (x{err['count']})")
        if sl.get("values"):
            lines.append("  Values:")
            for key, v in sl["values"].items():
                lines.append(f"    {key}: min={v['min']} max={v['max']} last={v['last']} count={v['count']}")
        if sl.get("tags_seen"):
            lines.append(f"  Tags seen: {', '.join(sl['tags_seen'])}")
        lines.append("")

        # Serial config
        lines.append("Serial Config:")
        if self.serial:
            bm = self.serial.get("boot_marker")
            lines.append(f"  Boot marker: {bm if bm else 'N/A'}")
            lines.append(f"  Success markers: {self.serial.get('success_markers', [])}")
            lines.append(f"  Error markers: {self.serial.get('error_markers', [])}")
        else:
            lines.append("  N/A — scan not run")
        lines.append("")

        # Project
        lines.append("Project:")
        lines.append(f"  Logging API: {self.project.get('logging_api') or 'N/A'}")
        dz = self.project.get("danger_zones", [])
        lines.append(f"  Danger zones: {len(dz)}")
        sz = self.project.get("safe_zones", [])
        lines.append(f"  Safe zones: {len(sz)}")
        lines.append("")

        # Instrumentation
        lines.append("Instrumentation:")
        inst = self.instrumentation
        lines.append(f"  Active: {inst.get('active_count', 0)}")
        fm = inst.get("files_modified", [])
        if fm:
            lines.append(f"  Files: {', '.join(fm)}")
        lines.append("")

        # Device
        lines.append("Device:")
        dev = self.device
        lines.append(f"  Boot count: {dev.get('boot_count_in_session', 0)}")
        uptime = dev.get("uptime_estimate_seconds")
        if uptime is not None:
            lines.append(f"  Uptime estimate: {uptime:.1f}s")
        else:
            lines.append("  Uptime estimate: N/A — no boot marker")
        lines.append("")

        return "\n".join(lines)


def collect_status(
    project_dir: Path | str,
    port: str | None = None,
    baud: int | None = None,
) -> DebugStatus:
    """Assemble diagnostic snapshot from all sources."""
    project_dir = Path(project_dir)
    status = DebugStatus()

    # Load scan cache
    scan_cache = load_scan_cache(project_dir)

    # Serial config from scan
    boot_marker = None
    if scan_cache:
        status.serial = scan_cache.get("serial", {})
        boot_marker = status.serial.get("boot_marker")
        status.project = {
            "logging_api": scan_cache.get("logging_api", {}).get("primary"),
            "danger_zones": scan_cache.get("danger_zones", []),
            "safe_zones": scan_cache.get("safe_zones", []),
        }
    else:
        status.serial = None
        status.project = {
            "logging_api": None,
            "danger_zones": [],
            "safe_zones": [],
        }

    # Analyze serial log
    log_path = project_dir / ".edesto" / "debug-log.jsonl"
    status.serial_log = _analyze_serial_log(log_path, boot_marker=boot_marker)

    # Instrumentation
    manifest_data = load_instrument_manifest(project_dir)
    if manifest_data:
        entries = manifest_data.get("entries", [])
        files = list(set(e.get("file", "") for e in entries))
        status.instrumentation = {
            "active_count": len(entries),
            "files_modified": files,
            "additions": entries,
        }
    else:
        status.instrumentation = {
            "active_count": 0,
            "files_modified": [],
            "additions": [],
        }

    # Tools
    try:
        from edesto_dev.debug_tools import detect_debug_tools
        tools_available = detect_debug_tools()
    except Exception:
        tools_available = []

    board_name = None
    try:
        from edesto_dev.config import load_project_config
        config = load_project_config(project_dir)
        port = port or config.serial.port
        baud = baud or config.serial.baud_rate
    except Exception:
        pass

    gdb = _detect_gdb_binary(board_name)

    status.tools = {
        "serial": port is not None,
        "saleae": "saleae" in tools_available,
        "openocd": "openocd" in tools_available,
        "gdb": gdb,
        "scope": "scope" in tools_available,
    }

    # Device
    boot_count = status.serial_log.get("resets_detected", 0)
    uptime = None
    if boot_marker and boot_count > 0:
        last_boot_ts = status.serial_log.get("last_boot_ts")
        last_output_ts = status.serial_log.get("last_output_ts")
        if last_boot_ts and last_output_ts:
            from datetime import datetime
            try:
                t_boot = datetime.fromisoformat(last_boot_ts)
                t_last = datetime.fromisoformat(last_output_ts)
                uptime = (t_last - t_boot).total_seconds()
            except (ValueError, TypeError):
                pass

    status.device = {
        "board": board_name,
        "port": port,
        "boot_count_in_session": boot_count,
        "uptime_estimate_seconds": uptime,
    }

    return status


def _analyze_serial_log(log_path: Path, *, boot_marker: str | None) -> dict:
    """Read debug-log.jsonl and aggregate statistics."""
    result = {
        "source": str(log_path),
        "total_lines": 0,
        "errors": [],
        "warnings": [],
        "tags_seen": [],
        "last_output_ts": None,
        "seconds_since_last_output": None,
        "resets_detected": 0,
        "values": {},
        "last_boot_ts": None,
    }

    if not log_path.exists():
        return result

    error_map: dict[str, dict] = {}  # raw message -> {count, first_ts, last_ts}
    tags = set()
    values: dict[str, dict] = {}

    with open(log_path) as f:
        for line_str in f:
            line_str = line_str.strip()
            if not line_str:
                continue
            try:
                entry = json.loads(line_str)
            except json.JSONDecodeError:
                continue

            result["total_lines"] += 1
            ts = entry.get("ts")
            raw = entry.get("raw", "")
            tag = entry.get("tag")
            data = entry.get("data", {})

            if ts:
                result["last_output_ts"] = ts

            # Tag tracking
            if tag:
                tags.add(tag)

            # Boot marker detection
            if boot_marker and boot_marker in raw:
                result["resets_detected"] += 1
                result["last_boot_ts"] = ts

            # Error detection
            if tag == "ERROR" or "[ERROR]" in raw:
                if raw not in error_map:
                    error_map[raw] = {"message": raw, "count": 0, "first_ts": ts, "last_ts": ts}
                error_map[raw]["count"] += 1
                error_map[raw]["last_ts"] = ts

            # Value tracking from data dict
            if isinstance(data, dict):
                for key, val in data.items():
                    if key == "message":
                        continue
                    try:
                        numeric = float(val)
                    except (ValueError, TypeError):
                        continue
                    if key not in values:
                        values[key] = {"min": numeric, "max": numeric, "last": numeric, "count": 0}
                    v = values[key]
                    v["count"] += 1
                    v["last"] = numeric
                    if numeric < v["min"]:
                        v["min"] = numeric
                    if numeric > v["max"]:
                        v["max"] = numeric

    result["errors"] = list(error_map.values())
    result["tags_seen"] = sorted(tags)

    # Convert float values to int where possible
    for key, v in values.items():
        for field in ("min", "max", "last"):
            if v[field] == int(v[field]):
                v[field] = int(v[field])
    result["values"] = values

    return result


def _detect_gdb_binary(board_name: str | None) -> str | None:
    """Return the correct GDB binary for the given board."""
    if board_name is None:
        return None
    name = board_name.lower()
    if "esp32" in name:
        for suffix in ("c3", "c6", "h2"):
            if suffix in name:
                return "riscv32-esp-elf-gdb"
        return "xtensa-esp-elf-gdb"
    return "arm-none-eabi-gdb"
