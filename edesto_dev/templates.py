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
        _debugging(port, baud_rate, boot_delay, tools, board_name=board_name, jtag_config=jtag_config),
        _troubleshooting(port, baud_rate, boot_delay),
        _datasheets(board_name),
        _rtos_guidance(toolchain_name, board_name),
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


def _debugging(port: str | None, baud_rate: int, boot_delay: int, debug_tools: list[str], board_name: str = "", jtag_config: JtagConfig | None = None) -> str:
    parts = []

    # Header with tool guide
    tool_guide = []
    if port:
        tool_guide.append(
            "- **Serial** — bidirectional communication: read application output and send commands to trigger firmware behavior"
        )
    if "saleae" in debug_tools:
        tool_guide.append(
            "- **Logic analyzer** — protocol-level issues (SPI/I2C timing, signal integrity, bus decoding)"
        )
    if "openocd" in debug_tools:
        tool_guide.append(
            "- **JTAG/SWD (TCL RPC)** — CPU-level issues (crashes, HardFaults, register/memory state via raw addresses)"
        )
        tool_guide.append(
            "- **GDB** — source-level debugging (symbolic breakpoints, backtraces with function names, variable inspection, stepping)"
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
        parts.append(_serial_section(port, baud_rate, boot_delay, debug_tools=debug_tools))

    # Tool subsections (conditional)
    if "saleae" in debug_tools:
        parts.append(_saleae_section())
    if "openocd" in debug_tools:
        parts.append(_openocd_section(jtag_config))
        parts.append(_gdb_section(board_name, jtag_config))
    if "scope" in debug_tools:
        parts.append(_scope_section())

    # edesto CLI tools reference
    parts.append(_edesto_commands_section())

    return "\n".join(s for s in parts if s)


def _serial_section(port: str, baud_rate: int, boot_delay: int, debug_tools: list[str] | None = None) -> str:
    parts = [f"""
### Serial Communication

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

#### Sending Commands

Use this Python snippet to send commands to the board and read the response:

```python
import serial, time, sys

try:
    ser = serial.Serial('{port}', {baud_rate}, timeout=1)
except serial.SerialException as err:
    print("Could not open {port}: " + str(err))
    sys.exit(1)

time.sleep({boot_delay})  # Wait for boot

# Wait for [READY] before sending
start = time.time()
while time.time() - start < 10:
    line = ser.readline().decode('utf-8', errors='ignore').strip()
    if line == '[READY]':
        break
else:
    print("Timed out waiting for [READY]")
    ser.close()
    sys.exit(1)

# Send a command (newline-terminated)
command = "read_sensor"
ser.write((command + "\\n").encode())
ser.flush()

# Read response until [DONE] or timeout
lines = []
start = time.time()
while time.time() - start < 10:
    line = ser.readline().decode('utf-8', errors='ignore').strip()
    if line:
        lines.append(line)
        print(line)
        if line == '[DONE]':
            break
ser.close()
```

Save this as `send_command.py` and run with `python send_command.py`. Adapt the command, timeout, and read duration as needed.

**Important serial conventions for your firmware:**
- Configure your serial port at {baud_rate} baud
- Send complete lines (newline-terminated) so each message can be parsed
- Print `[READY]` when initialization is complete
- Print `[ERROR] <description>` for any error conditions
- Use tags for structured output: `[SENSOR] temp=23.4`, `[STATUS] running`
- Print `[DONE]` when a test sequence finishes (allows the reader to exit early)
- Echo received commands with `[CMD] <command>` so the agent can confirm what was received
- Print `[OK]` after successful command execution
- Command flow example: send `read_sensor\\n` → firmware prints `[CMD] read_sensor`, `[SENSOR] temp=23.4`, `[OK]`, `[DONE]`"""]

    # Multi-step validation workflows (only when other debug tools are available)
    tools = debug_tools or []
    workflow_parts = []
    if "saleae" in tools:
        workflow_parts.append("""
##### Serial + Logic Analyzer

Send a command via serial to trigger a peripheral operation, then capture the bus traffic with the logic analyzer to verify the protocol-level behavior:

1. Start a Saleae capture (see Logic Analyzer section)
2. Send the command via serial (e.g., `spi_write\\n`)
3. Wait for `[DONE]` on serial
4. Stop the capture and export decoded protocol data
5. Compare the decoded bus traffic against expected values""")
    if "scope" in tools:
        workflow_parts.append("""
##### Serial + Oscilloscope

Send a command via serial to trigger an electrical output, then measure it with the oscilloscope:

1. Configure the oscilloscope trigger and timebase (see Oscilloscope section)
2. Send the command via serial (e.g., `start_pwm\\n`)
3. Wait for `[OK]` on serial
4. Read oscilloscope measurements (frequency, duty cycle, Vpp)
5. Compare against expected values from the firmware configuration""")
    if "openocd" in tools:
        workflow_parts.append("""
##### Serial + JTAG/GDB

Send a command via serial and use GDB to inspect CPU state when something goes wrong:

1. Set a GDB breakpoint at the function under test
2. Send the command via serial (e.g., `init_peripheral\\n`)
3. When the breakpoint hits, inspect variables and registers
4. Continue execution and check serial output for `[OK]` or `[ERROR]`""")

    if workflow_parts:
        parts.append("""
#### Multi-Step Validation Workflows

Combine serial commands with other debug tools for end-to-end validation:""")
        parts.extend(workflow_parts)

    return "\n".join(parts)


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


def _openocd_section(jtag_config: JtagConfig | None = None) -> str:
    if jtag_config:
        iface = jtag_config.interface
        target = jtag_config.target
        start_block = f"""
**Start OpenOCD** (run in a separate terminal — it stays running as a server):

```bash
openocd -f interface/{iface}.cfg -f target/{target}.cfg
```

**Auto-start from Python** — use this snippet to ensure OpenOCD is running before connecting:

```python
import subprocess, socket, time

def ensure_openocd(interface="{iface}", target="{target}"):
    \"\"\"Start OpenOCD if not already running.\"\"\"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(("localhost", 6666))
        s.close()
        return None  # Already running
    except (ConnectionRefusedError, OSError):
        pass
    proc = subprocess.Popen(
        ["openocd", "-f", f"interface/{{interface}}.cfg", "-f", f"target/{{target}}.cfg"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(1)  # Wait for server to start
    return proc  # Caller can proc.terminate() when done
```"""
    else:
        start_block = """
**Start OpenOCD** (run in a separate terminal — it stays running as a server):

```bash
openocd -f interface/cmsis-dap.cfg -f target/stm32f4x.cfg
```

Replace the interface and target config files to match your debug probe and chip. Common interfaces: `cmsis-dap.cfg`, `stlink.cfg`, `jlink.cfg`. Common targets: `stm32f4x.cfg`, `nrf52.cfg`, `esp32.cfg`, `rp2040.cfg`."""

    flash_iface = jtag_config.interface if jtag_config else "cmsis-dap"
    flash_target = jtag_config.target if jtag_config else "stm32f4x"

    return f"""
### JTAG/SWD: Direct Memory & Register Access

Use OpenOCD to inspect CPU state, read registers and memory, diagnose crashes, and flash firmware. This is the right tool when the board crashes, stops responding, hits a HardFault, or you need to inspect peripheral registers directly.
{start_block}

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
openocd -f interface/{flash_iface}.cfg -f target/{flash_target}.cfg \\
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


def _gdb_binary_for_board(board_name: str) -> str:
    """Return the correct GDB binary for the given board."""
    name = board_name.lower()
    if "esp32" in name:
        # ESP32-C3, C6, H2 are RISC-V; all others are Xtensa
        for suffix in ("c3", "c6", "h2"):
            if suffix in name:
                return "riscv32-esp-elf-gdb"
        return "xtensa-esp-elf-gdb"
    return "arm-none-eabi-gdb"


def _gdb_section(board_name: str, jtag_config: JtagConfig | None = None) -> str:
    """GDB source-level debugging section."""
    gdb = _gdb_binary_for_board(board_name)

    if jtag_config:
        iface = jtag_config.interface
        target = jtag_config.target
        openocd_setup = f"""Before connecting GDB, ensure OpenOCD is running (see the `ensure_openocd()` helper above, or start it manually):

```bash
openocd -f interface/{iface}.cfg -f target/{target}.cfg
```"""
    else:
        openocd_setup = """Before connecting GDB, ensure OpenOCD is running:

```bash
openocd -f interface/<probe>.cfg -f target/<chip>.cfg
```"""

    return f"""
### GDB: Source-Level Debugging

Use GDB when you need **source-level** insight: symbolic breakpoints, backtraces with function names and line numbers, local variable inspection, and stepping through C code. The TCL RPC section above is better for quick register/memory reads at known addresses; GDB is better for understanding *why* code misbehaves.

**GDB binary for this board:** `{gdb}`

**Compile with debug symbols** — add `-g` to your compiler flags (e.g., `-DCMAKE_BUILD_TYPE=Debug` or `build_flags = -g` in platformio.ini). Without `-g`, GDB can still show assembly and registers but not source lines or variable names.

{openocd_setup}

#### Batch Mode (Recommended for Automation)

Run a single GDB command sequence and exit. Ideal for quick checks — the agent can parse stdout directly:

```bash
{gdb} -batch -ex "target remote :3333" -ex "monitor reset halt" -ex "bt" build/firmware.elf
```

Multiple `-ex` flags chain commands:

```bash
{gdb} -batch \\
  -ex "target remote :3333" \\
  -ex "monitor reset halt" \\
  -ex "info registers" \\
  -ex "bt full" \\
  build/firmware.elf
```

#### Script Mode

For reusable command sequences, write a `.gdb` file and run with `-x`:

```
# debug_session.gdb
target remote :3333
monitor reset halt
break main
continue
bt full
info locals
quit
```

```bash
{gdb} -batch -x debug_session.gdb build/firmware.elf
```

#### Interactive Python Subprocess

For multi-step investigations where you need to read GDB output, make decisions, and send the next command:

```python
import subprocess

proc = subprocess.Popen(
    ["{gdb}", "--interpreter=mi2", "-q", "build/firmware.elf"],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    text=True,
)

def gdb_cmd(cmd):
    proc.stdin.write(cmd + "\\n")
    proc.stdin.flush()
    output = []
    while True:
        line = proc.stdout.readline()
        if not line or line.strip() == "(gdb)":
            break
        output.append(line.strip())
    return "\\n".join(output)

gdb_cmd("target remote :3333")
gdb_cmd("monitor reset halt")
bt = gdb_cmd("bt full")
print(bt)
# ... decide next action based on bt output ...
proc.terminate()
```

#### Essential GDB Commands

| Command | Description |
|---|---|
| `target remote :3333` | Connect to OpenOCD GDB server |
| `monitor reset halt` | Reset board and halt (via OpenOCD) |
| `break <func>` or `break file.c:line` | Set a breakpoint by symbol or source location |
| `next` | Step over (execute one source line) |
| `step` | Step into (enter function calls) |
| `finish` | Run until current function returns |
| `continue` | Resume execution |
| `bt` | Backtrace — show call stack with function names |
| `bt full` | Backtrace with local variables at each frame |
| `print <var>` | Print a variable's value |
| `info locals` | Show all local variables in current frame |
| `info args` | Show function arguments |
| `info registers` | Show CPU registers |
| `x/Nxw <addr>` | Examine N words of memory at address |
| `watch <var>` | Hardware watchpoint — break when variable changes |
| `monitor reset halt` | Reset and halt (via OpenOCD monitor command) |

#### Iterative Debugging

**Key principle:** OpenOCD stays running as a persistent server. Each GDB batch invocation is independent — run many in sequence, each building on findings from the previous one. Treat debugging as an iterative investigation, not a one-shot operation.

**Decision tree — what symptom are you seeing?**

```
Board crashes / HardFault / stops responding
  → Run Crash Investigation workflow
  → Backtrace shows crash in peripheral_init()?
      → Chain to: Peripheral Not Responding workflow
  → Backtrace shows crash with bad pointer?
      → Chain to: Watchpoint workflow (watch the pointer variable)
  → Backtrace shows crash with wrong value from sensor?
      → Chain to: Variable Tracing workflow

Wrong output values / incorrect behavior
  → Run Variable Tracing workflow
  → Variable correct at entry but wrong after calculation?
      → Use step/next to narrow down the exact line
  → Variable already wrong when received from peripheral?
      → Chain to: Peripheral Not Responding workflow

Peripheral not responding / no data
  → Run Peripheral Not Responding workflow
  → Registers configured correctly but no response?
      → Check with oscilloscope/logic analyzer for electrical issues
  → Register values don't match what was written?
      → Chain to: Watchpoint workflow (watch the config register address)

Intermittent / timing issues
  → Run Watchpoint workflow with conditional breakpoints
  → Watchpoint triggers in ISR context?
      → Check ISR-safety rules (FreeRTOS FromISR variants, etc.)
```

**Chaining example** — a concrete multi-step investigation:

```bash
# Step 1: Crash investigation reveals crash in spi_transfer()
{gdb} -batch -ex "target remote :3333" -ex "bt full" build/firmware.elf
# Output: #0 spi_transfer (data=0x0) at src/spi.c:45  ← null pointer!

# Step 2: Who set data to NULL? Trace it with a watchpoint
{gdb} -batch -ex "target remote :3333" -ex "monitor reset halt" \\
  -ex "watch spi_tx_buffer" -ex "continue" -ex "bt" build/firmware.elf
# Output: Hardware watchpoint hit — called from sensor_read() at src/sensor.c:23

# Step 3: Step through sensor_read() to see why buffer is NULL
{gdb} -batch -ex "target remote :3333" -ex "monitor reset halt" \\
  -ex "break sensor_read" -ex "continue" \\
  -ex "info locals" -ex "next" -ex "info locals" -ex "next" -ex "info locals" \\
  build/firmware.elf
# Output: buffer was allocated but freed early due to error path

# Step 4: Agent now knows the root cause — fix the code
```

#### Workflow: Crash Investigation

When the board crashes, hits a HardFault, or stops responding:

```bash
# 1. Get backtrace and register state
{gdb} -batch \\
  -ex "target remote :3333" \\
  -ex "bt full" \\
  -ex "info registers" \\
  build/firmware.elf

# 2. Read Cortex-M fault status registers
{gdb} -batch \\
  -ex "target remote :3333" \\
  -ex "x/1xw 0xE000ED28" \\
  -ex "x/1xw 0xE000ED2C" \\
  build/firmware.elf

# 3. Set breakpoint before crash location and rerun
{gdb} -batch \\
  -ex "target remote :3333" \\
  -ex "monitor reset halt" \\
  -ex "break <crash_function>" \\
  -ex "continue" \\
  -ex "info locals" \\
  -ex "next" -ex "info locals" \\
  -ex "next" -ex "info locals" \\
  build/firmware.elf
```

#### Workflow: Variable/Sensor Tracing

When outputs are wrong or sensor values are unexpected:

```bash
# Break at the function and print variables on each call
{gdb} -batch \\
  -ex "target remote :3333" \\
  -ex "monitor reset halt" \\
  -ex "break sensor_read" \\
  -ex "commands" -ex "info locals" -ex "info args" -ex "continue" -ex "end" \\
  -ex "continue" \\
  build/firmware.elf
```

#### Workflow: Peripheral Not Responding

When a peripheral (SPI, I2C, UART, etc.) doesn't respond or returns wrong data:

```bash
# 1. Break at peripheral init and step through register writes
{gdb} -batch \\
  -ex "target remote :3333" \\
  -ex "monitor reset halt" \\
  -ex "break peripheral_init" \\
  -ex "continue" \\
  -ex "info locals" \\
  -ex "next" -ex "next" -ex "next" \\
  -ex "info locals" \\
  build/firmware.elf

# 2. Examine peripheral status register (replace address from datasheet)
{gdb} -batch \\
  -ex "target remote :3333" \\
  -ex "x/1xw 0x40013000" \\
  build/firmware.elf

# 3. Check clock enable bits (RCC peripheral clock register)
{gdb} -batch \\
  -ex "target remote :3333" \\
  -ex "x/1xw 0x40023844" \\
  build/firmware.elf
```

Compare register values with the datasheet. Common issues: clock not enabled, wrong alternate-function mapping, incorrect prescaler.

#### Workflow: Watchpoints & Conditional Breakpoints

For intermittent issues, data corruption, or race conditions:

```bash
# Watch a variable — break when it changes
{gdb} -batch \\
  -ex "target remote :3333" \\
  -ex "monitor reset halt" \\
  -ex "watch my_variable" \\
  -ex "continue" \\
  -ex "bt" -ex "info locals" \\
  build/firmware.elf

# Conditional breakpoint — only break when condition is true
{gdb} -batch \\
  -ex "target remote :3333" \\
  -ex "monitor reset halt" \\
  -ex "break my_func if counter > 100" \\
  -ex "continue" \\
  -ex "info locals" \\
  build/firmware.elf
```"""


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


def _datasheets(board_name: str) -> str:
    parts = ["""
## Datasheets

Before writing or debugging firmware, check for datasheets in this project.

### Finding Datasheets

1. **Check `datasheets/` folder first** — if it exists, read any relevant PDFs.
2. **Check `docs/` and `hardware/` folders** for reference manuals, errata, and application notes.
3. **Search the project root and all subfolders** for any `.pdf` files that may be component datasheets or reference manuals.

### Extracting Key Information

When implementing a peripheral driver or configuring hardware, extract and use:

- **Register maps and bit-field definitions** — get the exact register addresses, field positions, and reset values. Never guess register addresses or bit positions.
- **Pin configurations and alternate functions** — verify which GPIO pins support the peripheral you need and what alternate-function mapping is required.
- **Timing diagrams and protocol specifications** — check setup/hold times, clock polarity/phase, and protocol framing.
- **Electrical characteristics** — voltage levels, maximum current per pin, absolute maximum ratings, and recommended operating conditions.
- **Initialization sequences** — many peripherals require a specific power-up or configuration sequence. Follow the datasheet order exactly.
- **Clock tree and prescaler settings** — verify the peripheral clock source and required divider values for your target frequency.

### Cross-Referencing Documents

If the project contains multiple documents (e.g., a reference manual AND a datasheet AND an errata sheet), use all of them:

- **Reference manual** — detailed register descriptions and peripheral operation.
- **Datasheet** — pinout, electrical characteristics, package information, and ordering codes.
- **Errata / silicon bugs** — known hardware issues that may require software workarounds. Always check for errata before finalizing a driver.
- **Application notes** — recommended configurations and design patterns from the manufacturer.

### Citing Datasheet Sections

When writing code based on datasheet information, add comments referencing the source:

```c
// See RM0090 Section 8.3.3 — SPI CR1 register
SPI1->CR1 = SPI_CR1_MSTR | SPI_CR1_BR_1;  // Master mode, fPCLK/8
```

This makes it easy to verify the code against the documentation later."""]

    # Board-family-specific guidance
    family_hint = _datasheet_family_hint(board_name)
    if family_hint:
        parts.append(family_hint)

    return "\n".join(parts)


def _datasheet_family_hint(board_name: str) -> str:
    """Return datasheet navigation tips tailored to the board family."""
    name = board_name.lower()

    if "stm32" in name:
        return """
### STM32 Reference Manual Structure

STM32 documentation is split across multiple documents:

- **Reference Manual (RMxxxx)** — the primary document for register-level programming. Each peripheral has its own chapter with register maps, bit-field tables, and functional descriptions. Look for "Register Map" summary tables at the end of each peripheral chapter.
- **Datasheet** — pinout tables (alternate function mapping), electrical specs, and package info. The "Alternate Function Mapping" table is essential for pin configuration.
- **Errata Sheet (ESxxxx)** — lists silicon bugs by device revision. Check the revision printed on your chip against the errata.
- **Programming Manual (PMxxxx)** — Cortex-M core details, instruction set, and system peripherals (NVIC, SysTick, MPU).

Key sections to look for: "GPIO alternate function mapping", "RCC clock tree", "Peripheral register map summary"."""

    if "esp32" in name or "esp8266" in name:
        return """
### ESP32 Technical Reference Structure

ESP32 documentation is organized as:

- **Technical Reference Manual (TRM)** — register-level details for each peripheral. Chapters are organized by peripheral (GPIO, SPI, I2C, etc.) with register description tables.
- **Datasheet** — pin definitions, electrical characteristics, RF specifications, and module pinouts.
- **Errata** — known issues per chip revision.
- **ESP-IDF Programming Guide** — higher-level API documentation and configuration options (complements the TRM).

Key sections to look for: "IO MUX and GPIO Matrix", "Register Summary" tables at the end of each peripheral chapter."""

    if "nrf" in name or "nordic" in name:
        return """
### Nordic nRF Documentation Structure

Nordic nRF documentation is organized as:

- **Product Specification** — the primary register-level document. Combines what STM32 splits into reference manual and datasheet. Each peripheral chapter includes register tables, bit-field descriptions, and functional overview.
- **Errata** — silicon anomalies listed by chip revision and severity. Check the "Scope" column to see if an anomaly affects your specific chip revision.
- **Infocenter / DevZone** — application notes and community-verified workarounds.

Key sections to look for: "Register overview" tables, "Instantiation" tables (base addresses per peripheral instance), "Pin configuration" chapter for GPIO setup."""

    return ""


def _rtos_guidance(toolchain_name: str, board_name: str) -> str:
    """Return RTOS-specific guidance based on toolchain and board."""
    name = toolchain_name.lower()
    if name == "zephyr":
        return _zephyr_rtos_section()
    if name == "espidf":
        return _freertos_section()
    if name == "arduino" and "esp32" in board_name.lower():
        return _freertos_section()
    return ""


def _freertos_section() -> str:
    return """
## RTOS

This project runs on **FreeRTOS**. All application code executes inside FreeRTOS tasks.

### Core Concepts

- **Tasks** are the basic unit of execution — each task has its own stack, priority, and state (running, ready, blocked, suspended).
- The **scheduler** is preemptive by default: a higher-priority task that becomes ready will immediately preempt a lower-priority one.
- **Tick rate** (`configTICK_RATE_HZ`, typically 1000) determines the time resolution for delays and timeouts.
- Priority numbers: higher number = higher priority. `tskIDLE_PRIORITY` (0) is the lowest.

### Task Creation

```c
// Basic task creation
xTaskCreate(
    task_function,    // Function pointer
    "TaskName",       // Debug name
    2048,             // Stack size (bytes on ESP32, words on other ports)
    NULL,             // Parameter passed to task
    5,                // Priority
    &task_handle      // Handle (can be NULL if not needed)
);

// ESP32-specific: pin task to a core (0 or 1)
xTaskCreatePinnedToCore(
    task_function, "TaskName", 2048, NULL, 5, &task_handle,
    1  // Core ID: 0 = protocol core, 1 = application core
);
```

### Synchronization Primitives

**Semaphores** — signaling between tasks or from ISRs:
```c
SemaphoreHandle_t sem = xSemaphoreCreateBinary();
xSemaphoreGive(sem);                              // Signal
xSemaphoreTake(sem, pdMS_TO_TICKS(1000));         // Wait (up to 1s)
```

**Mutexes** — protect shared resources (supports priority inheritance):
```c
SemaphoreHandle_t mtx = xSemaphoreCreateMutex();
xSemaphoreTake(mtx, portMAX_DELAY);  // Lock
// ... critical section ...
xSemaphoreGive(mtx);                 // Unlock
```

**Queues** — pass data between tasks:
```c
QueueHandle_t q = xQueueCreate(10, sizeof(int));
int val = 42;
xQueueSend(q, &val, portMAX_DELAY);               // Send
xQueueReceive(q, &val, pdMS_TO_TICKS(500));        // Receive
```

### Timers

```c
TimerHandle_t timer = xTimerCreate(
    "MyTimer", pdMS_TO_TICKS(1000), pdTRUE,  // 1s, auto-reload
    NULL, timer_callback
);
xTimerStart(timer, 0);
```

### ISR Rules

**Critical:** ISR functions must use `FromISR` variants of all FreeRTOS API calls:
```c
void IRAM_ATTR my_isr(void *arg) {
    BaseType_t xHigherPriorityTaskWoken = pdFALSE;
    xSemaphoreGiveFromISR(sem, &xHigherPriorityTaskWoken);
    portYIELD_FROM_ISR(xHigherPriorityTaskWoken);
}
```
- Never call `xSemaphoreTake()`, `xQueueSend()`, or any blocking function in an ISR — use `xSemaphoreGiveFromISR()`, `xQueueSendFromISR()`, etc.
- Always check `xHigherPriorityTaskWoken` and call `portYIELD_FROM_ISR()` to trigger a context switch if needed.

### Common Pitfalls

- **Stack overflow** — enable `configCHECK_FOR_STACK_OVERFLOW` (set to 2) during development. A stack overflow silently corrupts memory and causes random crashes.
- **Priority inversion** — use mutexes (not binary semaphores) for resource protection; mutexes support priority inheritance.
- **Watchdog starvation** — on ESP32, the idle task feeds the watchdog. If a high-priority task never blocks, the watchdog triggers. Always include a `vTaskDelay()` or blocking call in long-running loops.
- **`vTaskDelay()` vs `vTaskDelayUntil()`** — `vTaskDelay()` delays *from now*; `vTaskDelayUntil()` delays *from the last wake time*, giving more precise periodic timing.
- **Forgetting `portMAX_DELAY`** — passing `0` as timeout means "don't wait" and returns immediately if the resource isn't available."""


def _zephyr_rtos_section() -> str:
    return """
## RTOS

This project runs on **Zephyr RTOS**. All application code executes inside Zephyr threads.

### Core Concepts

- **Threads** are the basic unit of execution — each thread has its own stack, priority, and scheduling policy.
- **Priority model**: lower number = higher priority. Negative priorities are cooperative (never preempted), non-negative are preemptive.
- **Cooperative threads** (priority < 0) run until they explicitly yield or block — useful for critical sections.
- **Preemptive threads** (priority >= 0) can be preempted by higher-priority threads at any time.

### Thread Creation

```c
// Static thread definition (preferred — allocated at compile time)
K_THREAD_STACK_DEFINE(my_stack, 1024);
struct k_thread my_thread_data;

k_thread_create(&my_thread_data, my_stack,
    K_THREAD_STACK_SIZEOF(my_stack),
    my_thread_fn,        // Entry point
    NULL, NULL, NULL,    // Up to 3 arguments
    5,                   // Priority (lower = higher priority)
    0,                   // Options (0 or K_ESSENTIAL, K_FP_REGS, etc.)
    K_NO_WAIT            // Start delay (K_NO_WAIT = start immediately)
);

// Compile-time thread definition (even simpler)
K_THREAD_DEFINE(my_tid, 1024, my_thread_fn, NULL, NULL, NULL, 5, 0, 0);
```

### Synchronization Primitives

**Semaphores** — signaling between threads or from ISRs:
```c
K_SEM_DEFINE(my_sem, 0, 1);          // Static (initial=0, limit=1)
k_sem_give(&my_sem);                  // Signal
k_sem_take(&my_sem, K_MSEC(1000));   // Wait (up to 1s)
```

**Mutexes** — protect shared resources (supports priority inheritance):
```c
K_MUTEX_DEFINE(my_mutex);
k_mutex_lock(&my_mutex, K_FOREVER);  // Lock
// ... critical section ...
k_mutex_unlock(&my_mutex);           // Unlock
```

**Message Queues** — pass data between threads:
```c
K_MSGQ_DEFINE(my_msgq, sizeof(int), 10, 4);  // 10 items, 4-byte aligned
int val = 42;
k_msgq_put(&my_msgq, &val, K_FOREVER);       // Send
k_msgq_get(&my_msgq, &val, K_MSEC(500));     // Receive
```

### Work Queues

Defer processing to a worker thread (useful for offloading work from ISRs):
```c
struct k_work my_work;

void work_handler(struct k_work *work) {
    // Runs in system work queue thread
}

k_work_init(&my_work, work_handler);
k_work_submit(&my_work);  // ISR-safe
```

### Timers

```c
K_TIMER_DEFINE(my_timer, timer_expiry_fn, NULL);
k_timer_start(&my_timer, K_MSEC(1000), K_MSEC(1000));  // Initial delay, period
```

### Logging

Zephyr has a built-in logging subsystem — prefer it over `printk()`:
```c
#include <zephyr/logging/log.h>
LOG_MODULE_REGISTER(my_module, LOG_LEVEL_INF);

LOG_INF("System started, version %d", version);
LOG_ERR("Failed to read sensor: %d", err);
LOG_DBG("Raw value: 0x%04x", raw);
```
Enable in `prj.conf`: `CONFIG_LOG=y`

### Kconfig (`prj.conf`)

Kernel features are enabled via Kconfig options in `prj.conf`:
```
CONFIG_GPIO=y
CONFIG_I2C=y
CONFIG_SPI=y
CONFIG_LOG=y
CONFIG_SERIAL=y
CONFIG_CONSOLE=y
CONFIG_UART_CONSOLE=y
```
If a subsystem API returns `-ENOTSUP` or a header is missing, the Kconfig option is likely not enabled.

### Device Tree

Hardware is described in `.dts` and `.overlay` files, accessed in code via macros:
```c
#include <zephyr/drivers/gpio.h>
#define LED_NODE DT_NODELABEL(led0)
static const struct gpio_dt_spec led = GPIO_DT_SPEC_GET(LED_NODE, gpios);
```
Use `.overlay` files in your project to customize pin assignments without modifying board-level `.dts` files.

### ISR Rules

- `k_sem_give()` is ISR-safe — use it to signal threads from interrupt handlers.
- `k_mutex_lock()` is **NOT** ISR-safe — never call it from an ISR.
- Use `k_work_submit()` to defer complex processing from ISRs to a work queue thread.

### Common Pitfalls

- **Stack sizing** — use `K_THREAD_STACK_DEFINE()` and size generously during development. Enable `CONFIG_THREAD_ANALYZER=y` to monitor stack usage.
- **Missing Kconfig options** — forgetting to enable `CONFIG_*` options is the #1 cause of build errors and missing functionality. If an API call doesn't compile or returns an error, check Kconfig first.
- **Priority confusion** — Zephyr uses lower number = higher priority (opposite of FreeRTOS). Priority 0 is higher than priority 5.
- **Cooperative vs preemptive** — cooperative threads (negative priority) are never preempted. If your thread never yields, no other thread of equal or lower priority will run.
- **Device tree mismatches** — if `DT_NODELABEL()` returns a build error, the label doesn't exist in the device tree. Check the board's `.dts` file or add an `.overlay`.
- **Forgetting `K_FOREVER` vs `K_NO_WAIT`** — `K_FOREVER` blocks until available, `K_NO_WAIT` returns immediately with an error if unavailable. Choose deliberately."""


def _edesto_commands_section() -> str:
    """Generate the edesto CLI tools reference for SKILLS.md."""
    return """
### edesto CLI Tools

Use these commands instead of writing Python serial scripts:

| Command | Description |
|---|---|
| `edesto serial read` | Read serial output (auto-parses tags, logs to `.edesto/`) |
| `edesto serial send <CMD>` | Send a command and read response (auto-detects markers) |
| `edesto serial monitor` | Stream serial output continuously |
| `edesto serial ports` | List available serial ports with board labels |
| `edesto debug scan` | Scan source files for logging APIs, markers, ISR zones |
| `edesto debug instrument <FILE:LINE> --expr <EXPR> [--fmt <FMT>]` | Insert a debug print at a specific line |
| `edesto debug instrument --function <NAME>` | Add entry/exit logging to a function |
| `edesto debug instrument --gpio <FILE:LINE>` | Insert GPIO toggle for timing measurement |
| `edesto debug clean [--dry-run]` | Remove all instrumentation (EDESTO_TEMP_DEBUG markers) |
| `edesto debug status [--json]` | Show diagnostic snapshot (log analysis, tools, device state) |
| `edesto debug reset` | Clear all debug state files |
| `edesto config <KEY> <VALUE>` | Set a config value in edesto.toml |
| `edesto config <KEY>` | Get a config value |
| `edesto config --list` | Show all config values |

**Serial command options:** `--port`, `--baud` (override edesto.toml), `--json` (structured output), `--duration`, `--until` (stop on marker).

**Instrumentation safety rules:**
- All inserted lines are marked with `// EDESTO_TEMP_DEBUG` for guaranteed cleanup
- Instrumentation is refused in ISR/danger zones (use `--gpio` for timing in ISRs, or `--force` to override)
- `edesto debug clean` removes ALL instrumented lines — always run before committing
- Configure debug GPIO pin: `edesto config debug.gpio <PIN>`

**Debug workflow:**
1. `edesto debug scan` — analyze the project (auto-runs on first `serial read`)
2. `edesto serial read` / `edesto serial send <CMD>` — observe behavior
3. `edesto debug instrument ...` — add targeted debug output if needed
4. Compile and flash, then `edesto serial read` to check
5. `edesto debug clean` — remove instrumentation when done
6. `edesto debug status` — get a structured diagnostic snapshot for complex issues"""
