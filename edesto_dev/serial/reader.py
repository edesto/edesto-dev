"""Core I/O logic for serial read, send, and monitor operations."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from edesto_dev.serial.parser import LineParser, ParsedLine


@dataclass
class ReadResult:
    lines: list[str] = field(default_factory=list)
    parsed_lines: list[ParsedLine] = field(default_factory=list)
    duration_seconds: float = 0.0
    exit_reason: str = ""


@dataclass
class SendResult:
    lines: list[str] = field(default_factory=list)
    parsed_lines: list[ParsedLine] = field(default_factory=list)
    duration_seconds: float = 0.0
    exit_reason: str = ""
    exit_code: int = 0
    was_error: bool = False


def serial_read(
    ser,
    *,
    duration: float = 10,
    until: str | None = None,
    parser: LineParser | None = None,
    log_path: Path | str | None = None,
    quiet_timeout: float | None = None,
) -> ReadResult:
    """Read serial lines until condition met."""
    if parser is None:
        parser = LineParser()
    if log_path is not None:
        log_path = Path(log_path)

    lines: list[str] = []
    parsed: list[ParsedLine] = []
    start = time.monotonic()
    last_data = time.monotonic()
    exit_reason = "duration"

    log_file = open(log_path, "a") if log_path else None
    try:
        while True:
            elapsed = time.monotonic() - start
            if elapsed >= duration:
                exit_reason = "duration"
                break

            raw = ser.readline()
            if raw:
                line = raw.decode("utf-8", errors="ignore").strip()
                last_data = time.monotonic()
                lines.append(line)
                ts = datetime.now(timezone.utc).isoformat()
                parsed_line = parser.parse_line(line, ts)
                parsed.append(parsed_line)

                if log_file:
                    log_file.write(json.dumps(parsed_line.to_dict()) + "\n")

                if until and until in line:
                    exit_reason = "until_matched"
                    break
            else:
                # No data
                if quiet_timeout and (time.monotonic() - last_data) >= quiet_timeout:
                    exit_reason = "quiet_timeout"
                    break
    finally:
        if log_file:
            log_file.close()

    return ReadResult(
        lines=lines,
        parsed_lines=parsed,
        duration_seconds=time.monotonic() - start,
        exit_reason=exit_reason,
    )


def serial_send(
    ser,
    command: str,
    *,
    line_terminator: str = "\n",
    wait_ready: str | None = None,
    ready_timeout: float = 10,
    strip_echo: bool = False,
    until: str | None = None,
    success_markers: list[str] | None = None,
    error_markers: list[str] | None = None,
    quiet_timeout: float = 0.5,
    parser: LineParser | None = None,
    log_path: Path | str | None = None,
    timeout: float = 10,
) -> SendResult:
    """Send a command and read response."""
    if parser is None:
        parser = LineParser()
    if log_path is not None:
        log_path = Path(log_path)

    success_markers = success_markers or []
    error_markers = error_markers or []

    start = time.monotonic()

    # Wait for ready marker if requested
    if wait_ready:
        ready_start = time.monotonic()
        while time.monotonic() - ready_start < ready_timeout:
            raw = ser.readline()
            if raw:
                line = raw.decode("utf-8", errors="ignore").strip()
                if wait_ready in line:
                    break
        # If timeout, proceed anyway (log warning but don't hang)

    # Send command
    ser.write((command + line_terminator).encode())
    ser.flush()

    # Read response
    lines: list[str] = []
    parsed: list[ParsedLine] = []
    exit_reason = "timeout"
    exit_code = 0
    was_error = False
    last_data = time.monotonic()

    log_file = open(log_path, "a") if log_path else None
    try:
        while True:
            elapsed = time.monotonic() - start
            if elapsed >= timeout:
                exit_reason = "timeout"
                break

            raw = ser.readline()
            if raw:
                line = raw.decode("utf-8", errors="ignore").strip()
                last_data = time.monotonic()

                # Strip echo
                if strip_echo and line == command and not lines:
                    continue

                ts = datetime.now(timezone.utc).isoformat()
                parsed_line = parser.parse_line(line, ts)
                lines.append(line)
                parsed.append(parsed_line)

                if log_file:
                    log_file.write(json.dumps(parsed_line.to_dict()) + "\n")

                # Check markers
                for marker in success_markers:
                    if marker in line:
                        exit_reason = "success_marker"
                        exit_code = 0
                        break
                else:
                    for marker in error_markers:
                        if marker in line:
                            exit_reason = "error_marker"
                            exit_code = 1
                            was_error = True
                            break
                    else:
                        # Check until
                        if until and until in line:
                            exit_reason = "until_matched"
                            break
                        continue
                    break
                if exit_reason in ("success_marker", "error_marker"):
                    break
            else:
                # No data
                if quiet_timeout and (time.monotonic() - last_data) >= quiet_timeout:
                    exit_reason = "quiet_timeout"
                    break
    finally:
        if log_file:
            log_file.close()

    return SendResult(
        lines=lines,
        parsed_lines=parsed,
        duration_seconds=time.monotonic() - start,
        exit_reason=exit_reason,
        exit_code=exit_code,
        was_error=was_error,
    )


def serial_monitor(
    ser,
    *,
    duration: float | None = None,
    parser: LineParser | None = None,
    log_path: Path | str | None = None,
    output_callback=None,
) -> None:
    """Continuous read loop until KeyboardInterrupt or duration expires."""
    if parser is None:
        parser = LineParser()
    if log_path is not None:
        log_path = Path(log_path)
    if output_callback is None:
        output_callback = print

    start = time.monotonic()
    log_file = open(log_path, "a") if log_path else None
    try:
        while True:
            if duration and (time.monotonic() - start) >= duration:
                break

            raw = ser.readline()
            if raw:
                line = raw.decode("utf-8", errors="ignore").strip()
                ts = datetime.now(timezone.utc).isoformat()
                parsed_line = parser.parse_line(line, ts)
                output_callback(line)

                if log_file:
                    log_file.write(json.dumps(parsed_line.to_dict()) + "\n")
    except KeyboardInterrupt:
        pass
    finally:
        if log_file:
            log_file.close()
