"""SKILLS.md template rendering for edesto-dev."""

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
    setup_info: str | None = None,
    debug_tools: list[str] | None = None,
) -> str:
    """Render a complete SKILLS.md from generic parameters."""
    sections = [
        _generic_header(board_name, toolchain_name, port, baud_rate),
        _setup(setup_info),
        _generic_commands(compile_command, upload_command, monitor_command),
        _generic_dev_loop(compile_command, upload_command, boot_delay),
        _debugging(port, baud_rate, boot_delay, debug_tools or []),
        _troubleshooting(port, baud_rate, boot_delay),
        _datasheets(),
        _generic_board_info(board_name, board_info),
    ]
    return "\n".join(s for s in sections if s)


def render_template(board: Board, port: str) -> str:
    """Render SKILLS.md for an Arduino board (legacy helper)."""
    setup = None
    if board.core_url:
        setup = f"arduino-cli core install {board.core} --additional-urls {board.core_url}"
    elif board.core:
        setup = f"arduino-cli core install {board.core}"
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
        setup_info=setup,
        debug_tools=None,
    )


def render_from_toolchain(toolchain, board, port: str) -> str:
    """Render SKILLS.md using a Toolchain and Board."""
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
        setup_info=toolchain.setup_info(board),
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


def _setup(setup_info: str | None) -> str:
    if not setup_info:
        return ""
    return f"""
## Setup

Before compiling, ensure your toolchain is configured:

```
{setup_info}
```"""


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
6. **Validate your changes** using the debugging methods below. Pick the right tool for what you're checking.
7. If validation fails, go back to step 1 and iterate."""


def _debugging(port: str, baud_rate: int, boot_delay: int, debug_tools: list[str]) -> str:
    parts = []

    # Header with tool guide
    tool_guide = [
        "- **Serial output** — application-level behavior (sensor readings, state machines, error messages)"
    ]
    if "saleae" in debug_tools:
        tool_guide.append(
            "- **Logic analyzer** — protocol-level issues (SPI/I2C timing, signal integrity, bus decoding)"
        )
    if "openocd" in debug_tools:
        tool_guide.append(
            "- **JTAG/SWD** — CPU-level issues (crashes, HardFaults, register/memory state, breakpoints)"
        )
    if "scope" in debug_tools:
        tool_guide.append(
            "- **Oscilloscope** — electrical issues (voltage levels, PWM frequency/duty, rise times, noise)"
        )

    guide_text = "\n".join(tool_guide)
    parts.append(f"""
## Debugging

Use the right tool for the problem:
{guide_text}""")

    # Serial subsection (always present)
    parts.append(_serial_section(port, baud_rate, boot_delay))

    # Tool subsections (conditional) — stubs for now
    if "saleae" in debug_tools:
        parts.append(_saleae_section())
    if "openocd" in debug_tools:
        parts.append(_openocd_section())
    if "scope" in debug_tools:
        parts.append(_scope_section())

    return "\n".join(s for s in parts if s)


def _serial_section(port: str, baud_rate: int, boot_delay: int) -> str:
    return f"""
### Serial Output

This is how you verify your code is actually working on the device. Always validate after flashing.

Use this Python snippet to capture serial output from the board:

```python
import serial, time, sys

try:
    ser = serial.Serial('{port}', {baud_rate}, timeout=1)
except serial.SerialException as err:
    print("Could not open {port}: " + str(err))
    print("Check: is another process using the port? (serial monitor, screen, another script)")
    sys.exit(1)

time.sleep({boot_delay})  # Wait for boot
lines = []
start = time.time()
while time.time() - start < 10:  # Read for up to 10 seconds
    line = ser.readline().decode('utf-8', errors='ignore').strip()
    if line:
        lines.append(line)
        print(line)
        if line == '[DONE]':
            break
ser.close()
```

Save this as `read_serial.py` and run with `python read_serial.py`. Parse the output to check if your firmware is behaving correctly. Adapt the timeout and read duration as needed — some operations (WiFi connect, sensor warm-up) take longer than 10 seconds.

**Important serial conventions for your firmware:**
- Configure your serial port at {baud_rate} baud
- Send complete lines (newline-terminated) so each message can be parsed
- Print `[READY]` when initialization is complete
- Print `[ERROR] <description>` for any error conditions
- Use tags for structured output: `[SENSOR] temp=23.4`, `[STATUS] running`
- Print `[DONE]` when a test sequence finishes (allows the reader to exit early)"""


def _saleae_section() -> str:
    return ""


def _openocd_section() -> str:
    return ""


def _scope_section() -> str:
    return ""


def _troubleshooting(port: str, baud_rate: int, boot_delay: int) -> str:
    return f"""
## Troubleshooting

**Upload fails / "connection timeout":**
- Close any serial monitors or scripts that have the port open. Only one process can use `{port}` at a time.
- Try unplugging and re-plugging the USB cable.
- Some boards require holding the BOOT button during upload — check the pitfalls section below.

**No serial output after flashing:**
- Verify the baud rate in your firmware matches {baud_rate}.
- Ensure your firmware actually prints to serial (e.g., `Serial.begin({baud_rate})` or equivalent).
- Wait at least {boot_delay} seconds after flashing — the board needs time to reboot.

**Garbage characters on serial:**
- Almost always a baud rate mismatch. Ensure both firmware and the read script use {baud_rate}.

**"Permission denied" on serial port:**
- Linux: add your user to the `dialout` group: `sudo usermod -aG dialout $USER` (logout/login required).
- macOS: install the USB-serial driver for your board's chip (CP2102, CH340, etc.)."""


def _generic_board_info(board_name: str, board_info: dict) -> str:
    parts = [f"\n## {board_name}-Specific Information"]

    # Capabilities — merge with includes when both are present
    capabilities = board_info.get("capabilities")
    includes = board_info.get("includes")
    if not isinstance(includes, dict):
        includes = {}

    if capabilities:
        if isinstance(capabilities, dict):
            # Dict of capability -> include directive (legacy style)
            parts.append("\n### Capabilities")
            for cap, include in capabilities.items():
                parts.append(f"- {cap.replace('_', ' ').title()}: `{include}`")
        elif isinstance(capabilities, list):
            parts.append("\n### Capabilities")
            for cap in capabilities:
                include = includes.get(cap)
                if include:
                    parts.append(f"- {cap.replace('_', ' ').title()}: `{include}`")
                else:
                    parts.append(f"- {cap.replace('_', ' ').title()}")

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
