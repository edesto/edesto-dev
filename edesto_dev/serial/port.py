"""Serial port utilities for edesto-dev."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import serial
import serial.tools.list_ports
from serial.tools.list_ports import comports

from edesto_dev.config import load_project_config


@dataclass
class PortInfo:
    device: str
    description: str
    hwid: str
    board_label: str | None = None


class SerialError(Exception):
    """Structured serial error with exit code."""

    def __init__(self, message: str, exit_code: int = 1):
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code

    def to_dict(self) -> dict:
        return {"error": self.message, "exit_code": self.exit_code}


def list_serial_ports() -> list[PortInfo]:
    """List available serial ports with board labels."""
    ports = []
    for p in comports():
        ports.append(PortInfo(
            device=p.device,
            description=p.description,
            hwid=p.hwid,
        ))
    return ports


def open_serial(port: str, baud_rate: int, timeout: float = 1) -> serial.Serial:
    """Open a serial port with structured error handling.

    Exit codes:
        0: success
        2: port not found / device disconnected
        3: port busy
        4: permission denied
    """
    try:
        return serial.Serial(port, baud_rate, timeout=timeout)
    except PermissionError as e:
        raise SerialError(str(e), exit_code=4) from e
    except serial.SerialException as e:
        msg = str(e).lower()
        if "busy" in msg or "resource" in msg:
            raise SerialError(str(e), exit_code=3) from e
        raise SerialError(str(e), exit_code=2) from e


def resolve_port_and_baud(
    cli_port: str | None,
    cli_baud: int | None,
    project_dir: Path | str,
) -> tuple[str, int]:
    """Resolve port and baud rate from CLI flags or config.

    Resolution order: CLI flag > edesto.toml > error.
    """
    port = cli_port
    baud = cli_baud

    if port is None or baud is None:
        try:
            config = load_project_config(project_dir)
            if port is None:
                port = config.serial.port
            if baud is None:
                baud = config.serial.baud_rate
        except FileNotFoundError:
            pass

    if port is None:
        import click
        raise click.UsageError(
            "No serial port specified. Use --port or set serial.port in edesto.toml"
        )

    if baud is None:
        baud = 115200

    return port, baud
