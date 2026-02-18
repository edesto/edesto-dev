"""CLAUDE.md template rendering for edesto-dev."""

from __future__ import annotations

from edesto_dev.toolchain import Board


def render_generic_template(
    board_name: str,
    toolchain_name: str,
    port: str,
    baud_rate: int,
    compile_command: str,
    upload_command: str,
    monitor_command: str | None,
    boot_delay: int,
    board_info: dict,
) -> str:
    """Render a complete CLAUDE.md from generic (non-Arduino-specific) parameters."""
    sections = [
        _generic_header(board_name, toolchain_name, port, baud_rate),
        _generic_commands(compile_command, upload_command, monitor_command),
        _generic_dev_loop(compile_command, upload_command, boot_delay),
        _generic_validation(port, baud_rate, boot_delay),
        _datasheets(),
        _generic_board_info(board_name, board_info),
    ]
    return "\n".join(sections)


def render_template(board: Board, port: str) -> str:
    """Legacy: render CLAUDE.md for an Arduino board."""
    return render_generic_template(
        board_name=board.name,
        toolchain_name="Arduino",
        port=port,
        baud_rate=board.baud_rate,
        compile_command=f"arduino-cli compile --fqbn {board.fqbn} .",
        upload_command=f"arduino-cli upload --fqbn {board.fqbn} --port {port} .",
        monitor_command=f"arduino-cli monitor --port {port} --config baudrate={board.baud_rate}",
        boot_delay=3,
        board_info={
            "capabilities": board.includes if board.includes else None,
            "pin_notes": board.pin_notes if board.pin_notes else None,
            "pitfalls": board.pitfalls if board.pitfalls else None,
        },
    )


def render_from_toolchain(toolchain, board, port: str) -> str:
    """Render CLAUDE.md using a Toolchain and Board."""
    config = toolchain.serial_config(board)
    info = toolchain.board_info(board)
    return render_generic_template(
        board_name=board.name,
        toolchain_name=toolchain.name,
        port=port,
        baud_rate=config["baud_rate"],
        compile_command=toolchain.compile_command(board),
        upload_command=toolchain.upload_command(board, port),
        monitor_command=toolchain.monitor_command(board, port),
        boot_delay=config.get("boot_delay", 3),
        board_info=info,
    )


# ---------------------------------------------------------------------------
# Generic helper functions
# ---------------------------------------------------------------------------


def _generic_header(board_name: str, toolchain_name: str, port: str, baud_rate: int) -> str:
    return f"""# Embedded Development: {board_name}

You are developing firmware for a {board_name} connected via USB.

## Hardware
- Board: {board_name}
- Port: {port}
- Framework: {toolchain_name}
- Baud rate: {baud_rate}"""


def _generic_commands(
    compile_command: str,
    upload_command: str,
    monitor_command: str | None,
) -> str:
    parts = [f"""
## Commands

Compile:
```
{compile_command}
```

Flash:
```
{upload_command}
```"""]

    if monitor_command is not None:
        parts.append(f"""
Monitor:
```
{monitor_command}
```""")

    return "".join(parts)


def _generic_dev_loop(compile_command: str, upload_command: str, boot_delay: int) -> str:
    return f"""
## Development Loop

Every time you change code, follow this exact sequence:

1. Edit your firmware source files
2. Compile: `{compile_command}`
3. If compile fails, read the errors, fix them, and recompile. Do NOT flash broken code.
4. Flash: `{upload_command}`
5. Wait {boot_delay} seconds for the board to reboot.
6. **Validate your changes** using the method below.
7. If validation fails, go back to step 1 and iterate."""


def _generic_validation(port: str, baud_rate: int, boot_delay: int) -> str:
    return f"""
## Validation

This is how you verify your code is actually working on the device. Always validate after flashing.

### Read Serial Output

Use this Python snippet to capture serial output from the board:

```python
import serial, time
ser = serial.Serial('{port}', {baud_rate}, timeout=1)
time.sleep({boot_delay})  # Wait for boot
lines = []
start = time.time()
while time.time() - start < 10:  # Read for 10 seconds
    line = ser.readline().decode('utf-8', errors='ignore').strip()
    if line:
        lines.append(line)
        print(line)
ser.close()
```

Save this as `read_serial.py` and run with `python read_serial.py`. Parse the output to check if your firmware is behaving correctly.

**Important serial conventions for your firmware:**
- Configure your serial port at {baud_rate} baud
- Send complete lines (newline-terminated) so each message can be parsed
- Print `[READY]` when initialization is complete
- Print `[ERROR] <description>` for any error conditions
- Use tags for structured output: `[SENSOR] temp=23.4`, `[STATUS] running`"""


def _generic_board_info(board_name: str, board_info: dict) -> str:
    parts = [f"\n## {board_name}-Specific Information"]

    # Capabilities with includes
    capabilities = board_info.get("capabilities")
    if capabilities:
        if isinstance(capabilities, dict):
            # Dict of capability -> include directive (legacy Arduino style)
            parts.append("\n### Capabilities")
            for cap, include in capabilities.items():
                parts.append(f"- {cap.replace('_', ' ').title()}: `{include}`")
        elif isinstance(capabilities, list):
            # List of capability strings
            parts.append("\n### Capabilities")
            for cap in capabilities:
                parts.append(f"- {cap.replace('_', ' ').title()}")

    # Includes (separate from capabilities, used by render_from_toolchain)
    includes = board_info.get("includes")
    if includes and isinstance(includes, dict) and not isinstance(capabilities, dict):
        parts.append("\n### Includes")
        for cap, include in includes.items():
            parts.append(f"- {cap.replace('_', ' ').title()}: `{include}`")

    # Pin reference
    pin_notes = board_info.get("pin_notes")
    if pin_notes:
        parts.append("\n### Pin Reference")
        for note in pin_notes:
            parts.append(f"- {note}")

    # Pitfalls
    pitfalls = board_info.get("pitfalls")
    if pitfalls:
        parts.append("\n### Common Pitfalls")
        for pitfall in pitfalls:
            parts.append(f"- {pitfall}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _datasheets() -> str:
    return """
## Datasheets

Before writing or debugging firmware, check for datasheets in this project:

1. **Check `datasheets/` folder first** — if it exists, read any relevant PDFs for pin configurations, register maps, timing specs, and electrical limits.
2. **Check the project root and subfolders** for any other .pdf files that may be component datasheets or reference manuals.

When you find a datasheet:
- Read it to understand the hardware you're interfacing with.
- Use the correct register addresses, pin assignments, and protocol settings from the datasheet — not from memory or guesswork.
- Pay attention to voltage levels, max current ratings, and timing requirements.
- If a datasheet contradicts the pin reference below, the datasheet is correct."""
