"""SKILLS.md template rendering for edesto-dev."""

from __future__ import annotations

from edesto_dev.toolchain import Board, JtagConfig


def render_generic_template(
    board_name: str,
    toolchain_name: str,
    port: str | None,
    baud_rate: int,
    compile_command: str,
    upload_command: str,
    monitor_command: str | None,
    boot_delay: int,
    board_info: dict,
    setup_info: str | None = None,
    debug_tools: list[str] | None = None,
    jtag_config: JtagConfig | None = None,
) -> str:
    """Render a complete SKILLS.md from generic parameters."""
    tools = list(debug_tools or [])
    if jtag_config and "openocd" not in tools:
        tools.append("openocd")
    sections = [
        _generic_header(board_name, toolchain_name, port, baud_rate, jtag_config=jtag_config),
        _setup(setup_info),
        _generic_commands(compile_command, upload_command, monitor_command),
        _generic_dev_loop(compile_command, upload_command, boot_delay),
        _debugging(port, baud_rate, boot_delay, tools),
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


def render_from_toolchain(toolchain, board, port: str | None, debug_tools: list[str] | None = None, jtag_config: JtagConfig | None = None) -> str:
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
        debug_tools=debug_tools,
        jtag_config=jtag_config,
    )


# ---------------------------------------------------------------------------
# Generic helper functions
# ---------------------------------------------------------------------------


def _generic_header(board_name: str, toolchain_name: str, port: str | None, baud_rate: int, jtag_config: JtagConfig | None = None) -> str:
    if jtag_config:
        lines = [f"# Embedded Development: {board_name}",
                 "",
                 f"You are developing firmware for a {board_name} connected via JTAG/SWD.",
                 "",
                 "## Hardware",
                 f"- Board: {board_name}",
                 f"- Debug probe: {jtag_config.interface}",
                 f"- Framework: {toolchain_name}",
                 f"- Upload: openocd (JTAG/SWD)"]
        if port:
            lines.append(f"- Serial port: {port}")
            lines.append(f"- Baud rate: {baud_rate}")
        return "\n".join(lines)
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


def _debugging(port: str | None, baud_rate: int, boot_delay: int, debug_tools: list[str]) -> str:
    parts = []

    # Header with tool guide
    tool_guide = []
    if port:
        tool_guide.append(
            "- **Serial output** — application-level behavior (sensor readings, state machines, error messages)"
        )
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

    # Serial subsection (only when port is available)
    if port:
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
    return """
### Logic Analyzer

Use the Saleae Logic 2 automation API to capture and decode digital signals. This is the right tool when you need to verify SPI/I2C/UART protocol timing, decode bus traffic, or check signal edges.

```python
from saleae import automation
from pathlib import Path
import sys

OUTPUT_DIR = Path("saleae_capture")
OUTPUT_DIR.mkdir(exist_ok=True)

try:
    manager = automation.Manager.connect(port=10430)
except Exception as err:
    print("Could not connect to Saleae Logic 2: " + str(err))
    print("Ensure Logic 2 is running with: Logic --automation")
    sys.exit(1)

device_config = automation.LogicDeviceConfiguration(
    enabled_digital_channels=[0, 1, 2, 3],
    digital_sample_rate=10_000_000,
    digital_threshold_volts=3.3,
)

capture_config = automation.CaptureConfiguration(
    capture_mode=automation.TimedCaptureMode(duration_seconds=2.0)
)

with manager.start_capture(
    device_configuration=device_config,
    capture_configuration=capture_config,
) as capture:
    capture.wait()

    # Add a protocol analyzer — change to 'I2C', 'UART', etc. as needed
    spi = capture.add_analyzer('SPI', label='SPI Bus', settings={
        'MISO': 0,
        'Clock': 1,
        'Enable': 2,
        'Bits per Transfer': '8 Bits per Transfer (Standard)',
    })

    # Export decoded protocol data
    capture.export_data_table(
        filepath=str(OUTPUT_DIR / "decoded.csv"),
        analyzers=[spi],
    )

    # Export raw digital data
    capture.export_raw_data_csv(
        directory=str(OUTPUT_DIR),
        digital_channels=[0, 1, 2, 3],
    )

print("Capture saved to", OUTPUT_DIR)
# Read decoded.csv to check protocol data
import csv
with open(OUTPUT_DIR / "decoded.csv") as f:
    reader = csv.DictReader(f)
    for row in reader:
        print(row)
```

Adapt the channel numbers, sample rate, and protocol analyzer to match your wiring:
- **SPI**: typically 3-4 channels (MISO, CLK, CS, optionally MOSI)
- **I2C**: 2 channels (SDA, SCL)
- **UART**: 1 channel (TX or RX)

If the capture shows no transitions or unexpected data, ask the user to verify that the logic analyzer probes are connected to the correct pins and that the ground clip is attached."""


def _openocd_section() -> str:
    return """
### JTAG/SWD

Use OpenOCD to inspect CPU state, read registers and memory, diagnose crashes, and flash firmware. This is the right tool when the board crashes, stops responding, hits a HardFault, or you need to inspect peripheral registers directly.

**Start OpenOCD** (run in a separate terminal — it stays running as a server):

```bash
openocd -f interface/cmsis-dap.cfg -f target/stm32f4x.cfg
```

Replace the interface and target config files to match your debug probe and chip. Common interfaces: `cmsis-dap.cfg`, `stlink.cfg`, `jlink.cfg`. Common targets: `stm32f4x.cfg`, `nrf52.cfg`, `esp32.cfg`, `rp2040.cfg`.

**Connect and inspect** via the TCL RPC port (6666):

```python
import socket, sys

class OpenOCD:
    TERM = b"\\x1a"

    def __init__(self, host="localhost", port=6666, timeout=10.0):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect((host, port))
        except ConnectionRefusedError:
            print("Could not connect to OpenOCD on port 6666.")
            print("Start it with: openocd -f interface/<probe>.cfg -f target/<chip>.cfg")
            sys.exit(1)
        self.sock.settimeout(timeout)

    def cmd(self, command):
        self.sock.sendall(command.encode() + self.TERM)
        buf = b""
        while True:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("OpenOCD closed")
            buf += chunk
            if buf.endswith(self.TERM):
                break
        return buf[:-1].decode("utf-8", errors="replace").strip()

    def close(self):
        self.sock.close()

ocd = OpenOCD()

# Halt the CPU
ocd.cmd("halt")

# Read core registers
print("PC:", ocd.cmd("reg pc"))
print("SP:", ocd.cmd("reg sp"))
print("LR:", ocd.cmd("reg lr"))

# Read Cortex-M fault registers (fixed addresses, all Cortex-M3/M4/M7/M33)
print("CFSR:", ocd.cmd("mdw 0xE000ED28"))   # Configurable Fault Status
print("HFSR:", ocd.cmd("mdw 0xE000ED2C"))   # HardFault Status
print("MMFAR:", ocd.cmd("mdw 0xE000ED34"))  # MemManage Fault Address
print("BFAR:", ocd.cmd("mdw 0xE000ED38"))   # BusFault Address

# Read memory (e.g., 16 words starting at RAM base)
print("RAM:", ocd.cmd("mdw 0x20000000 16"))

# Resume execution
ocd.cmd("resume")
ocd.close()
```

**Common operations:**
- `halt` — stop the CPU
- `resume` — continue execution
- `step` — single-step one instruction
- `reg` — print all registers
- `reg pc` / `reg sp` / `reg lr` — read a specific register
- `mdw <addr> [count]` — read 32-bit words from memory
- `mww <addr> <value>` — write a 32-bit word to memory
- `bp <addr> 4 hw` — set a hardware breakpoint
- `rbp <addr>` — remove a breakpoint
- `flash write_image erase firmware.elf` — flash firmware
- `reset run` — reset and run from the start
- `reset halt` — reset and halt before any code runs

**One-shot flash and verify** (no persistent server needed):

```bash
openocd -f interface/cmsis-dap.cfg -f target/stm32f4x.cfg \\
  -c "program firmware.elf verify reset exit"
```

**Diagnosing a HardFault:** If CFSR is non-zero after a crash, decode the bits:
- Bit 25 (DIVBYZERO): divide by zero
- Bit 24 (UNALIGNED): unaligned memory access
- Bit 18 (INVPC): invalid PC on exception return
- Bit 17 (INVSTATE): invalid EPSR state (often a thumb bit issue)
- Bit 16 (UNDEFINSTR): undefined instruction
- Bit 15 (BFARVALID): BFAR holds the faulting address
- Bit 9 (IMPRECISERR): imprecise bus error
- Bit 8 (PRECISERR): precise bus error (BFAR valid)
- Bit 1 (DACCVIOL): data access violation
- Bit 0 (IACCVIOL): instruction access violation

If OpenOCD cannot connect or returns errors, ask the user to verify that the JTAG/SWD debug probe is connected to the board and that the correct interface/target config files are being used."""


def _scope_section() -> str:
    return """
### Oscilloscope

Use a SCPI-compatible oscilloscope to measure voltage levels, PWM frequency/duty cycle, signal timing, and rise times. This is the right tool when you need to verify electrical behavior — that a GPIO actually toggles, that a PWM is at the right frequency, or that voltage levels are within spec.

```python
import pyvisa
import sys

rm = pyvisa.ResourceManager()
resources = rm.list_resources()
if not resources:
    print("No oscilloscope found. Check USB or network connection.")
    sys.exit(1)

# Connect to the first detected instrument
scope = rm.open_resource(resources[0])
scope.timeout = 10000
print("Connected:", scope.query("*IDN?").strip())

# Configure for a 3.3V digital signal on Channel 1
scope.write(":CHANnel1:DISPlay ON")
scope.write(":CHANnel1:SCALe 1.0")       # 1 V/div
scope.write(":CHANnel1:OFFSet 1.65")     # Center 3.3V signal
scope.write(":CHANnel1:COUPling DC")

# Set trigger on rising edge at 1.65V (mid-VCC)
scope.write(":TRIGger:MODE EDGE")
scope.write(":TRIGger:EDGe:SOURce CHANnel1")
scope.write(":TRIGger:EDGe:SLOPe POSitive")
scope.write(":TRIGger:EDGe:LEVel 1.65")

# Set timebase (adjust for expected signal frequency)
scope.write(":TIMebase:SCALe 0.001")     # 1 ms/div

# Run and wait for trigger
scope.write(":RUN")
import time; time.sleep(2)

# Read measurements
scope.write(":MEASure:SOURce CHANnel1")
freq = scope.query(":MEASure:FREQuency?").strip()
duty = scope.query(":MEASure:DUTYcycle?").strip()
vpp  = scope.query(":MEASure:VPP?").strip()
vmax = scope.query(":MEASure:VMAX?").strip()
rise = scope.query(":MEASure:RISetime?").strip()

print("Frequency: " + freq + " Hz")
print("Duty cycle: " + duty + " %")
print("Vpp: " + vpp + " V")
print("Vmax: " + vmax + " V")
print("Rise time: " + rise + " s")

scope.write(":RUN")
scope.close()
```

Adapt the channel, voltage scale, timebase, and trigger level to match your signal. Common adjustments:
- **PWM at 1 kHz**: `:TIMebase:SCALe 0.0005` (500 us/div shows ~2 periods)
- **I2C at 400 kHz**: `:TIMebase:SCALe 0.000005` (5 us/div)
- **5V logic**: `:CHANnel1:SCALe 2.0`, trigger at 2.5V

**Vendor differences:** Rigol uses `:MEASure:FREQ?`, Keysight uses `:MEASure:FREQuency?`, Siglent uses `:MEASure:FREQuency?` on newer firmware. If a command returns an error, check your scope's programming guide.

If the scope shows no signal or unexpected readings, ask the user to verify that the oscilloscope probe is connected to the correct pin and that the ground clip is attached."""


def _troubleshooting(port: str | None, baud_rate: int, boot_delay: int) -> str:
    if not port:
        return ""
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
