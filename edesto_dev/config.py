"""Project configuration and state management for edesto-dev."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]


@dataclass
class SerialConfig:
    port: str | None = None
    baud_rate: int = 115200


@dataclass
class DebugConfig:
    gpio: int | None = None


@dataclass
class ProjectConfig:
    serial: SerialConfig = field(default_factory=SerialConfig)
    debug: DebugConfig = field(default_factory=DebugConfig)
    jtag: dict = field(default_factory=dict)
    toolchain: dict = field(default_factory=dict)


def load_project_config(project_dir: Path | str) -> ProjectConfig:
    """Parse edesto.toml and return a typed ProjectConfig."""
    project_dir = Path(project_dir)
    toml_path = project_dir / "edesto.toml"
    if not toml_path.exists():
        raise FileNotFoundError(f"edesto.toml not found in {project_dir}")

    if tomllib is None:
        raise ImportError("No TOML parser available (need Python 3.11+ or tomli)")

    with open(toml_path, "rb") as f:
        data = tomllib.load(f)

    serial_data = data.get("serial", {})
    debug_data = data.get("debug", {})

    serial = SerialConfig(
        port=serial_data.get("port"),
        baud_rate=serial_data.get("baud_rate", 115200),
    )
    debug = DebugConfig(
        gpio=debug_data.get("gpio"),
    )

    return ProjectConfig(
        serial=serial,
        debug=debug,
        jtag=data.get("jtag", {}),
        toolchain=data.get("toolchain", {}),
    )


def get_config_value(project_dir: Path | str, key: str):
    """Dotted key lookup, e.g. 'debug.gpio', 'serial.baud_rate'."""
    project_dir = Path(project_dir)
    toml_path = project_dir / "edesto.toml"
    if not toml_path.exists():
        return None

    if tomllib is None:
        return None

    with open(toml_path, "rb") as f:
        data = tomllib.load(f)

    parts = key.split(".", 1)
    if len(parts) == 2:
        section, k = parts
        return data.get(section, {}).get(k)
    return data.get(key)


def set_config_value(project_dir: Path | str, key: str, value) -> None:
    """Write a value to edesto.toml using line-based editing."""
    project_dir = Path(project_dir)
    toml_path = project_dir / "edesto.toml"

    # Coerce integer-like strings
    if isinstance(value, str):
        try:
            value = int(value)
        except ValueError:
            pass

    parts = key.split(".", 1)
    if len(parts) != 2:
        raise ValueError(f"Key must be dotted (section.key), got: {key}")
    section, k = parts

    # Format value for TOML
    if isinstance(value, int):
        val_str = str(value)
    elif isinstance(value, str):
        val_str = f'"{value}"'
    else:
        val_str = str(value)

    if toml_path.exists():
        lines = toml_path.read_text().splitlines(keepends=True)
    else:
        lines = []

    # Find the section and key
    section_header = f"[{section}]"
    section_idx = None
    key_idx = None
    next_section_idx = None

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == section_header:
            section_idx = i
        elif section_idx is not None and next_section_idx is None:
            if stripped.startswith("[") and stripped.endswith("]"):
                next_section_idx = i
            elif re.match(rf"^{re.escape(k)}\s*=", stripped):
                key_idx = i

    if key_idx is not None:
        # Update existing key
        lines[key_idx] = f"{k} = {val_str}\n"
    elif section_idx is not None:
        # Section exists, insert key after section header
        insert_at = next_section_idx if next_section_idx is not None else len(lines)
        # Insert before next section, find last non-empty line in section
        lines.insert(insert_at, f"{k} = {val_str}\n")
    else:
        # Create new section
        if lines and not lines[-1].endswith("\n"):
            lines.append("\n")
        if lines:
            lines.append("\n")
        lines.append(f"{section_header}\n")
        lines.append(f"{k} = {val_str}\n")

    toml_path.write_text("".join(lines))


def list_config(project_dir: Path | str) -> dict:
    """Return a flat dotted-key dict of all config values."""
    project_dir = Path(project_dir)
    toml_path = project_dir / "edesto.toml"
    if not toml_path.exists():
        return {}

    if tomllib is None:
        return {}

    with open(toml_path, "rb") as f:
        data = tomllib.load(f)

    result = {}
    for section, values in data.items():
        if isinstance(values, dict):
            for k, v in values.items():
                result[f"{section}.{k}"] = v
        else:
            result[section] = values
    return result


def ensure_edesto_dir(project_dir: Path | str) -> Path:
    """Create .edesto/ directory with .gitignore containing '*'."""
    project_dir = Path(project_dir)
    edesto_dir = project_dir / ".edesto"
    edesto_dir.mkdir(exist_ok=True)
    gitignore = edesto_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n")
    return edesto_dir


def load_scan_cache(project_dir: Path | str) -> dict | None:
    """Read .edesto/debug-scan.json."""
    path = Path(project_dir) / ".edesto" / "debug-scan.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def save_scan_cache(project_dir: Path | str, data: dict) -> None:
    """Write .edesto/debug-scan.json."""
    path = Path(project_dir) / ".edesto" / "debug-scan.json"
    ensure_edesto_dir(project_dir)
    path.write_text(json.dumps(data, indent=2))


def load_instrument_manifest(project_dir: Path | str) -> dict | None:
    """Read .edesto/instrument-manifest.json."""
    path = Path(project_dir) / ".edesto" / "instrument-manifest.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def save_instrument_manifest(project_dir: Path | str, data: dict) -> None:
    """Write .edesto/instrument-manifest.json."""
    path = Path(project_dir) / ".edesto" / "instrument-manifest.json"
    ensure_edesto_dir(project_dir)
    path.write_text(json.dumps(data, indent=2))


def append_debug_log(project_dir: Path | str, entry: dict) -> None:
    """Append a JSON line to .edesto/debug-log.jsonl, auto-truncate at 10MB."""
    project_dir = Path(project_dir)
    ensure_edesto_dir(project_dir)
    log_path = project_dir / ".edesto" / "debug-log.jsonl"

    max_size = 10 * 1024 * 1024  # 10MB

    # Check if truncation needed
    if log_path.exists() and log_path.stat().st_size > max_size:
        # Keep the last half of lines
        lines = log_path.read_text().splitlines(keepends=True)
        half = len(lines) // 2
        log_path.write_text("".join(lines[half:]))

    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def clear_debug_state(project_dir: Path | str) -> None:
    """Remove debug-log.jsonl, instrument-manifest.json, debug-scan.json."""
    project_dir = Path(project_dir)
    edesto_dir = project_dir / ".edesto"
    for name in ("debug-log.jsonl", "instrument-manifest.json", "debug-scan.json"):
        path = edesto_dir / name
        if path.exists():
            path.unlink()
