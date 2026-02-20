"""Debug instrumentation engine for edesto-dev."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


_SOURCE_EXTENSIONS = {".c", ".cpp", ".h", ".hpp", ".ino"}
_SKIP_DIRS = {"build", ".pio", ".git", "node_modules", ".edesto"}
_MARKER = "// EDESTO_TEMP_DEBUG"


@dataclass
class InstrumentManifest:
    entries: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"entries": self.entries}

    @classmethod
    def from_dict(cls, data: dict) -> InstrumentManifest:
        return cls(entries=data.get("entries", []))


@dataclass
class CleanResult:
    removed_count: int = 0
    removed_lines: list[str] = field(default_factory=list)
    orphan_warnings: list[str] = field(default_factory=list)


def _check_danger_zone(filepath: Path, line: int, project_dir: Path | None, force: bool) -> None:
    """Check if the target line is in a danger zone."""
    if project_dir is None or force:
        return

    scan_path = project_dir / ".edesto" / "debug-scan.json"
    if not scan_path.exists():
        return

    import json
    scan_data = json.loads(scan_path.read_text())
    danger_zones = scan_data.get("danger_zones", [])

    try:
        rel_path = str(filepath.relative_to(project_dir))
    except ValueError:
        rel_path = filepath.name

    for dz in danger_zones:
        if dz.get("file") == rel_path:
            line_range = dz.get("line_range", [0, 0])
            if line_range[0] <= line <= line_range[1]:
                raise ValueError(
                    f"Line {line} is in a danger zone ({dz.get('reason', 'unknown')}). "
                    f"Use --gpio for timing or --force to override."
                )


def instrument_line(
    filepath: Path | str,
    line: int,
    *,
    exprs: list[str],
    fmts: list[str] | None = None,
    logging_api: str,
    manifest: InstrumentManifest,
    project_dir: Path | str | None = None,
    force: bool = False,
) -> str:
    """Insert a debug log at the specified line."""
    filepath = Path(filepath)
    if project_dir:
        project_dir = Path(project_dir)
        _check_danger_zone(filepath, line, project_dir, force)

    lines = filepath.read_text().splitlines(keepends=True)

    # Build the debug statement
    debug_stmt = _build_debug_statement(exprs, fmts, logging_api)
    debug_line = f"    {debug_stmt} {_MARKER}\n"

    # Insert before the target line (0-indexed)
    lines.insert(line - 1, debug_line)
    filepath.write_text("".join(lines))

    manifest.entries.append({
        "file": str(filepath),
        "line": line,
        "content": debug_stmt,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return debug_stmt


def _build_debug_statement(exprs: list[str], fmts: list[str] | None, logging_api: str) -> str:
    """Build a debug print statement for the given logging API."""
    api_lower = logging_api.lower()

    if "serial" in api_lower:
        # Arduino: use String() concatenation, no fmt needed
        parts = []
        for expr in exprs:
            parts.append(f'{expr}=" + String({expr}) + "')
        msg = "EDESTO_DEBUG " + " ".join(parts)
        return f'Serial.println("{msg}");'

    # For printf, ESP_LOG*, LOG_INF/WRN/ERR: require fmts
    if not fmts or len(fmts) != len(exprs):
        raise ValueError(
            f"--fmt is required for each --expr with {logging_api} "
            f"(got {len(fmts or [])} fmts for {len(exprs)} exprs)"
        )

    fmt_parts = []
    for expr, fmt in zip(exprs, fmts):
        fmt_parts.append(f"{expr}={fmt}")
    fmt_str = "EDESTO_DEBUG " + " ".join(fmt_parts)
    expr_args = ", ".join(exprs)

    if "esp_log" in api_lower:
        return f'{logging_api}("EDESTO", "{fmt_str}\\n", {expr_args});'
    elif "log_" in api_lower:
        return f'{logging_api}("{fmt_str}", {expr_args});'
    else:
        # printf and similar
        return f'{logging_api}("{fmt_str}\\n", {expr_args});'


def instrument_function(
    filepath: Path | str,
    function_name: str,
    *,
    logging_api: str,
    manifest: InstrumentManifest,
) -> list[str]:
    """Add entry/exit logging to a function."""
    filepath = Path(filepath)
    content = filepath.read_text()
    lines = content.splitlines(keepends=True)

    # Find the function
    func_pattern = re.compile(rf"\b{re.escape(function_name)}\s*\(")
    func_line_idx = None
    brace_line_idx = None

    for i, line in enumerate(lines):
        if func_pattern.search(line) and func_line_idx is None:
            func_line_idx = i
            # Find opening brace
            for j in range(i, min(i + 5, len(lines))):
                if "{" in lines[j]:
                    brace_line_idx = j
                    break
            break

    if func_line_idx is None or brace_line_idx is None:
        raise ValueError(f"Function '{function_name}' not found in {filepath}")

    # Build entry/exit statements
    entry_stmt = _build_entry_exit_statement(function_name, ">>>", logging_api)
    exit_stmt = _build_entry_exit_statement(function_name, "<<<", logging_api)

    inserted = []

    # Find return statements and closing brace, insert exit before them
    # Process in reverse to maintain line indices
    close_brace_idx = None
    return_indices = []

    # Track brace depth to find the function's closing brace
    depth = 0
    for i in range(brace_line_idx, len(lines)):
        for ch in lines[i]:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    close_brace_idx = i
                    break
        if close_brace_idx is not None:
            break
        if depth >= 1 and "return" in lines[i]:
            stripped = lines[i].strip()
            if stripped.startswith("return"):
                return_indices.append(i)

    # Insert in reverse order to preserve indices
    insertions = []
    for idx in return_indices:
        insertions.append((idx, f"    {exit_stmt} {_MARKER}\n"))

    # Only add exit before closing brace if there's no return right before it
    if close_brace_idx is not None:
        # Check if the line before the closing brace is a return
        last_code_idx = close_brace_idx - 1
        while last_code_idx > brace_line_idx and not lines[last_code_idx].strip():
            last_code_idx -= 1
        last_line = lines[last_code_idx].strip() if last_code_idx > brace_line_idx else ""
        if not last_line.startswith("return") and close_brace_idx not in return_indices:
            insertions.append((close_brace_idx, f"    {exit_stmt} {_MARKER}\n"))

    # Sort insertions by line index in reverse
    insertions.sort(key=lambda x: x[0], reverse=True)
    for idx, stmt in insertions:
        lines.insert(idx, stmt)
        inserted.append(stmt)

    # Insert entry after opening brace
    entry_line = f"    {entry_stmt} {_MARKER}\n"
    lines.insert(brace_line_idx + 1, entry_line)
    inserted.append(entry_line)

    filepath.write_text("".join(lines))

    manifest.entries.append({
        "file": str(filepath),
        "function": function_name,
        "content": f"entry/exit logging for {function_name}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return inserted


def _build_entry_exit_statement(function_name: str, direction: str, logging_api: str) -> str:
    """Build an entry or exit log statement."""
    api_lower = logging_api.lower()
    msg = f"{direction} {function_name}"
    if "serial" in api_lower:
        return f'Serial.println("{msg}");'
    elif "esp_log" in api_lower:
        return f'ESP_LOGI("EDESTO", "{msg}");'
    elif "log_" in api_lower:
        return f'LOG_INF("{msg}");'
    else:
        return f'printf("{msg}\\n");'


def instrument_gpio(
    filepath: Path | str,
    line: int,
    *,
    gpio_pin: int | None,
    manifest: InstrumentManifest,
) -> str:
    """Insert GPIO toggle before and after the target line."""
    if gpio_pin is None:
        raise ValueError(
            "No debug gpio pin configured. Run: edesto config debug.gpio <PIN>"
        )

    filepath = Path(filepath)
    lines = filepath.read_text().splitlines(keepends=True)

    high_line = f"    digitalWrite({gpio_pin}, HIGH); {_MARKER}\n"
    low_line = f"    digitalWrite({gpio_pin}, LOW); {_MARKER}\n"

    # Insert LOW after the target line, HIGH before it
    lines.insert(line, low_line)  # After target (0-indexed: line = target_line_index + 1)
    lines.insert(line - 1, high_line)  # Before target

    filepath.write_text("".join(lines))

    manifest.entries.append({
        "file": str(filepath),
        "line": line,
        "content": f"GPIO toggle pin {gpio_pin}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return f"GPIO {gpio_pin} toggle"


def clean_all(
    project_dir: Path | str,
    *,
    file: Path | str | None = None,
    dry_run: bool = False,
) -> CleanResult:
    """Remove all lines marked with EDESTO_TEMP_DEBUG."""
    project_dir = Path(project_dir)
    removed_count = 0
    removed_lines = []
    orphan_warnings = []

    if file:
        files_to_scan = [Path(file)]
    else:
        files_to_scan = list(_iter_source_files(project_dir))

    for filepath in files_to_scan:
        content = filepath.read_text()
        if _MARKER not in content:
            continue

        lines = content.splitlines(keepends=True)
        new_lines = []
        for line in lines:
            if _MARKER in line:
                removed_count += 1
                removed_lines.append(line.strip())
                if not dry_run:
                    continue  # Skip this line
            new_lines.append(line)

        if not dry_run:
            filepath.write_text("".join(new_lines))

    return CleanResult(
        removed_count=removed_count,
        removed_lines=removed_lines,
        orphan_warnings=orphan_warnings,
    )


def _iter_source_files(scan_dir: Path):
    """Iterate source files for cleaning."""
    for filepath in scan_dir.rglob("*"):
        if not filepath.is_file():
            continue
        if filepath.suffix not in _SOURCE_EXTENSIONS:
            continue
        if any(part in _SKIP_DIRS for part in filepath.relative_to(scan_dir).parts):
            continue
        yield filepath
