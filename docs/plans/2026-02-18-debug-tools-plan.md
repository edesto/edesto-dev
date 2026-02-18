# Debug Tools Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add logic analyzer (Saleae), JTAG/SWD (OpenOCD), and oscilloscope (SCPI) support to edesto's SKILLS.md output, as equal peers alongside serial debugging.

**Architecture:** A new `detect_debug_tools()` function checks for installed packages/binaries. The template's `_generic_validation()` becomes `_debugging()` with conditional subsections per detected tool. Each subsection has a Python snippet the agent can adapt. The CLI passes detected tools to the renderer. `edesto doctor` reports tool status.

**Tech Stack:** Python sockets (OpenOCD TCL), `saleae.automation` (Saleae Logic 2), `pyvisa` (oscilloscopes). None are edesto dependencies — they're only checked for and referenced in snippets.

---

### Task 1: Create debug tool detection module

**Files:**
- Create: `edesto_dev/debug_tools.py`
- Test: `tests/test_debug_tools.py`

**Step 1: Write the failing tests**

```python
"""Tests for debug tool detection."""

from unittest.mock import patch

from edesto_dev.debug_tools import detect_debug_tools


class TestDetectDebugTools:
    def test_returns_list(self):
        result = detect_debug_tools()
        assert isinstance(result, list)

    @patch("edesto_dev.debug_tools.shutil.which", return_value="/usr/bin/openocd")
    @patch("edesto_dev.debug_tools._check_import", side_effect=lambda name: name == "saleae")
    def test_detects_openocd_and_saleae(self, mock_import, mock_which):
        result = detect_debug_tools()
        assert "openocd" in result
        assert "saleae" in result

    @patch("edesto_dev.debug_tools.shutil.which", return_value=None)
    @patch("edesto_dev.debug_tools._check_import", return_value=False)
    def test_empty_when_nothing_installed(self, mock_import, mock_which):
        result = detect_debug_tools()
        assert result == []

    @patch("edesto_dev.debug_tools.shutil.which", return_value=None)
    @patch("edesto_dev.debug_tools._check_import", side_effect=lambda name: name == "pyvisa")
    def test_detects_scope_only(self, mock_import, mock_which):
        result = detect_debug_tools()
        assert result == ["scope"]
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_debug_tools.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'edesto_dev.debug_tools'`

**Step 3: Write the implementation**

```python
"""Debug tool detection for edesto-dev."""

import shutil


def _check_import(module_name: str) -> bool:
    """Check if a Python module can be imported."""
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False


def detect_debug_tools() -> list[str]:
    """Detect available debug tools. Returns list of tool names.

    Checks:
    - "saleae": logic2-automation Python package installed
    - "openocd": openocd binary on PATH
    - "scope": pyvisa Python package installed
    """
    tools: list[str] = []

    if _check_import("saleae"):
        tools.append("saleae")

    if shutil.which("openocd"):
        tools.append("openocd")

    if _check_import("pyvisa"):
        tools.append("scope")

    return tools
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_debug_tools.py -v`
Expected: all 4 PASS

**Step 5: Commit**

```bash
git add edesto_dev/debug_tools.py tests/test_debug_tools.py
git commit -m "feat: add debug tool detection (saleae, openocd, scope)"
```

---

### Task 2: Refactor Validation into Debugging section with serial subsection

This task renames `_generic_validation` to `_debugging` and restructures it. Serial becomes a subsection. The function signature gains a `debug_tools` parameter for later tasks.

**Files:**
- Modify: `edesto_dev/templates.py:8-31` (render_generic_template) and `150-191` (_generic_validation)
- Modify: `tests/test_templates.py`

**Step 1: Write the failing test**

Add to `tests/test_templates.py` in `TestRenderTemplate`:

```python
    def test_has_debugging_section(self):
        board = get_board("esp32")
        result = render_template(board, port="/dev/ttyUSB0")
        assert "## Debugging" in result
        assert "### Serial Output" in result
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_templates.py::TestRenderTemplate::test_has_debugging_section -v`
Expected: FAIL — `AssertionError: assert '## Debugging' in result`

**Step 3: Implement the refactor**

In `edesto_dev/templates.py`:

1. Add `debug_tools: list[str] | None = None` parameter to `render_generic_template()`.

2. Replace the `_generic_validation(port, baud_rate, boot_delay)` call in the sections list with `_debugging(port, baud_rate, boot_delay, debug_tools or [])`.

3. Rename `_generic_validation` to `_debugging`. Restructure its content:

```python
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

    # Tool subsections (conditional)
    if "saleae" in debug_tools:
        parts.append(_saleae_section())
    if "openocd" in debug_tools:
        parts.append(_openocd_section())
    if "scope" in debug_tools:
        parts.append(_scope_section())

    return "\n".join(parts)
```

4. Extract the existing serial content into `_serial_section(port, baud_rate, boot_delay)` — same content as current `_generic_validation` but under `### Serial Output` heading instead of `## Validation` / `### Read Serial Output`.

5. Add stub functions for the three tool sections (return empty string for now — tasks 3-5 fill them in):

```python
def _saleae_section() -> str:
    return ""

def _openocd_section() -> str:
    return ""

def _scope_section() -> str:
    return ""
```

6. Update `render_template()` and `render_from_toolchain()` to pass `debug_tools=[]` (default, no tools detected in legacy path).

7. Update the Development Loop step 6 text from `**Validate your changes** using the method below.` to `**Validate your changes** using the debugging methods below. Pick the right tool for what you're checking.`

**Step 4: Fix existing tests**

Several existing tests assert `"## Validation"` or `"Validation"`. Update them:
- `test_has_serial_validation` → assert `"### Serial Output"` and `"serial.Serial"` and `"[READY]"`
- `TestAllBoardsRender::test_has_validation_section` → assert `"## Debugging"` and `"serial.Serial"`
- Other tests that check for `"Validation"` → change to `"Debugging"` or `"Serial Output"`

**Step 5: Run all tests**

Run: `pytest tests/ -v`
Expected: all pass (275+)

**Step 6: Commit**

```bash
git add edesto_dev/templates.py tests/test_templates.py
git commit -m "refactor: rename Validation to Debugging with Serial Output subsection"
```

---

### Task 3: Saleae logic analyzer template section

**Files:**
- Modify: `edesto_dev/templates.py` (_saleae_section)
- Test: `tests/test_templates.py`

**Step 1: Write the failing test**

Add to `tests/test_templates.py`:

```python
class TestDebugToolSections:
    def test_saleae_section_when_detected(self):
        from edesto_dev.templates import render_generic_template
        result = render_generic_template(
            board_name="ESP32",
            toolchain_name="arduino",
            port="/dev/ttyUSB0",
            baud_rate=115200,
            compile_command="compile",
            upload_command="upload",
            monitor_command=None,
            boot_delay=3,
            board_info={},
            debug_tools=["saleae"],
        )
        assert "### Logic Analyzer" in result
        assert "Manager.connect" in result
        assert "export_data_table" in result

    def test_saleae_section_absent_when_not_detected(self):
        from edesto_dev.templates import render_generic_template
        result = render_generic_template(
            board_name="ESP32",
            toolchain_name="arduino",
            port="/dev/ttyUSB0",
            baud_rate=115200,
            compile_command="compile",
            upload_command="upload",
            monitor_command=None,
            boot_delay=3,
            board_info={},
            debug_tools=[],
        )
        assert "### Logic Analyzer" not in result

    def test_saleae_has_connection_check_guidance(self):
        from edesto_dev.templates import render_generic_template
        result = render_generic_template(
            board_name="ESP32",
            toolchain_name="arduino",
            port="/dev/ttyUSB0",
            baud_rate=115200,
            compile_command="compile",
            upload_command="upload",
            monitor_command=None,
            boot_delay=3,
            board_info={},
            debug_tools=["saleae"],
        )
        assert "ask the user to verify" in result.lower() or "verify" in result.lower()
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_templates.py::TestDebugToolSections -v`
Expected: FAIL — first test fails because `_saleae_section` returns empty string

**Step 3: Implement `_saleae_section`**

```python
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
```

**Step 4: Run tests**

Run: `pytest tests/test_templates.py::TestDebugToolSections -v`
Expected: all 3 PASS

**Step 5: Commit**

```bash
git add edesto_dev/templates.py tests/test_templates.py
git commit -m "feat: add Saleae logic analyzer section to SKILLS.md template"
```

---

### Task 4: OpenOCD JTAG/SWD template section

**Files:**
- Modify: `edesto_dev/templates.py` (_openocd_section)
- Test: `tests/test_templates.py`

**Step 1: Write the failing test**

Add to `TestDebugToolSections`:

```python
    def test_openocd_section_when_detected(self):
        from edesto_dev.templates import render_generic_template
        result = render_generic_template(
            board_name="ESP32",
            toolchain_name="arduino",
            port="/dev/ttyUSB0",
            baud_rate=115200,
            compile_command="compile",
            upload_command="upload",
            monitor_command=None,
            boot_delay=3,
            board_info={},
            debug_tools=["openocd"],
        )
        assert "### JTAG/SWD" in result
        assert "OpenOCD" in result
        assert "CFSR" in result or "fault" in result.lower()

    def test_openocd_section_absent_when_not_detected(self):
        from edesto_dev.templates import render_generic_template
        result = render_generic_template(
            board_name="ESP32",
            toolchain_name="arduino",
            port="/dev/ttyUSB0",
            baud_rate=115200,
            compile_command="compile",
            upload_command="upload",
            monitor_command=None,
            boot_delay=3,
            board_info={},
            debug_tools=[],
        )
        assert "### JTAG/SWD" not in result
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_templates.py::TestDebugToolSections::test_openocd_section_when_detected -v`
Expected: FAIL

**Step 3: Implement `_openocd_section`**

```python
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
```

**Step 4: Run tests**

Run: `pytest tests/test_templates.py::TestDebugToolSections -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add edesto_dev/templates.py tests/test_templates.py
git commit -m "feat: add OpenOCD JTAG/SWD section to SKILLS.md template"
```

---

### Task 5: Oscilloscope SCPI template section

**Files:**
- Modify: `edesto_dev/templates.py` (_scope_section)
- Test: `tests/test_templates.py`

**Step 1: Write the failing test**

Add to `TestDebugToolSections`:

```python
    def test_scope_section_when_detected(self):
        from edesto_dev.templates import render_generic_template
        result = render_generic_template(
            board_name="ESP32",
            toolchain_name="arduino",
            port="/dev/ttyUSB0",
            baud_rate=115200,
            compile_command="compile",
            upload_command="upload",
            monitor_command=None,
            boot_delay=3,
            board_info={},
            debug_tools=["scope"],
        )
        assert "### Oscilloscope" in result
        assert "pyvisa" in result
        assert "FREQuency" in result or "frequency" in result.lower()

    def test_scope_section_absent_when_not_detected(self):
        from edesto_dev.templates import render_generic_template
        result = render_generic_template(
            board_name="ESP32",
            toolchain_name="arduino",
            port="/dev/ttyUSB0",
            baud_rate=115200,
            compile_command="compile",
            upload_command="upload",
            monitor_command=None,
            boot_delay=3,
            board_info={},
            debug_tools=[],
        )
        assert "### Oscilloscope" not in result
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_templates.py::TestDebugToolSections::test_scope_section_when_detected -v`
Expected: FAIL

**Step 3: Implement `_scope_section`**

```python
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

print(f"Frequency: {freq} Hz")
print(f"Duty cycle: {duty} %")
print(f"Vpp: {vpp} V")
print(f"Vmax: {vmax} V")
print(f"Rise time: {rise} s")

scope.write(":RUN")
scope.close()
```

Adapt the channel, voltage scale, timebase, and trigger level to match your signal. Common adjustments:
- **PWM at 1 kHz**: `:TIMebase:SCALe 0.0005` (500 us/div shows ~2 periods)
- **I2C at 400 kHz**: `:TIMebase:SCALe 0.000005` (5 us/div)
- **5V logic**: `:CHANnel1:SCALe 2.0`, trigger at 2.5V

**Vendor differences:** Rigol uses `:MEASure:FREQ?`, Keysight uses `:MEASure:FREQuency?`, Siglent uses `:MEASure:FREQuency?` on newer firmware. If a command returns an error, check your scope's programming guide.

If the scope shows no signal or unexpected readings, ask the user to verify that the oscilloscope probe is connected to the correct pin and that the ground clip is attached."""
```

**Step 4: Run tests**

Run: `pytest tests/test_templates.py::TestDebugToolSections -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add edesto_dev/templates.py tests/test_templates.py
git commit -m "feat: add oscilloscope SCPI section to SKILLS.md template"
```

---

### Task 6: Wire detection into CLI and template renderer

**Files:**
- Modify: `edesto_dev/cli.py:1-10` (imports) and `131` (render call)
- Modify: `edesto_dev/templates.py:59-74` (render_from_toolchain)
- Modify: `edesto_dev/templates.py:34-56` (render_template)
- Test: `tests/test_cli.py`

**Step 1: Write the failing test**

Add to `tests/test_cli.py`:

```python
class TestInitDebugTools:
    @patch("edesto_dev.cli.detect_debug_tools", return_value=["saleae", "openocd"])
    def test_init_includes_detected_debug_tools(self, mock_debug, runner):
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init", "--board", "esp32", "--port", "/dev/ttyUSB0"])
            assert result.exit_code == 0
            content = Path("SKILLS.md").read_text()
            assert "### Logic Analyzer" in content
            assert "### JTAG/SWD" in content
            assert "### Oscilloscope" not in content

    @patch("edesto_dev.cli.detect_debug_tools", return_value=[])
    def test_init_no_debug_tools(self, mock_debug, runner):
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init", "--board", "esp32", "--port", "/dev/ttyUSB0"])
            assert result.exit_code == 0
            content = Path("SKILLS.md").read_text()
            assert "### Serial Output" in content
            assert "### Logic Analyzer" not in content
            assert "### JTAG/SWD" not in content
            assert "### Oscilloscope" not in content
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py::TestInitDebugTools -v`
Expected: FAIL — `ImportError` or missing mock target

**Step 3: Implement the wiring**

In `edesto_dev/cli.py`:

1. Add import at the top (line 8 area):
```python
from edesto_dev.debug_tools import detect_debug_tools
```

2. After line 131 (`content = render_from_toolchain(toolchain, board_def, port=port)`), change to:
```python
    debug_tools = detect_debug_tools()
    content = render_from_toolchain(toolchain, board_def, port=port, debug_tools=debug_tools)
```

In `edesto_dev/templates.py`:

3. Update `render_from_toolchain` signature and body to accept and pass `debug_tools`:
```python
def render_from_toolchain(toolchain, board, port: str, debug_tools: list[str] | None = None) -> str:
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
    )
```

**Step 4: Run all tests**

Run: `pytest tests/ -v`
Expected: all pass

**Step 5: Commit**

```bash
git add edesto_dev/cli.py edesto_dev/templates.py tests/test_cli.py
git commit -m "feat: wire debug tool detection into CLI and template renderer"
```

---

### Task 7: Add debug tools to `edesto doctor`

**Files:**
- Modify: `edesto_dev/cli.py:172-207` (doctor command)
- Test: `tests/test_cli.py`

**Step 1: Write the failing test**

Add to `tests/test_cli.py`:

```python
class TestDoctorDebugTools:
    @patch("edesto_dev.cli.detect_debug_tools", return_value=["saleae", "openocd", "scope"])
    def test_doctor_shows_debug_tools(self, mock_debug, runner):
        result = runner.invoke(main, ["doctor"])
        assert "saleae" in result.output.lower()
        assert "openocd" in result.output.lower()
        assert "scope" in result.output.lower() or "oscilloscope" in result.output.lower()

    @patch("edesto_dev.cli.detect_debug_tools", return_value=[])
    def test_doctor_shows_no_debug_tools(self, mock_debug, runner):
        result = runner.invoke(main, ["doctor"])
        # Should mention debug tools are optional
        assert result.exit_code == 0
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py::TestDoctorDebugTools -v`
Expected: FAIL

**Step 3: Implement**

In the `doctor` command in `edesto_dev/cli.py`, add after the pyserial check (before the final summary):

```python
    # Check debug tools (optional)
    debug_tools = detect_debug_tools()
    click.echo("\nDebug tools (optional):")
    _TOOL_NAMES = {"saleae": "Saleae Logic 2 (logic2-automation)", "openocd": "OpenOCD (JTAG/SWD)", "scope": "Oscilloscope (pyvisa)"}
    for tool_id, tool_name in _TOOL_NAMES.items():
        if tool_id in debug_tools:
            click.echo(f"  [OK] {tool_name}")
        else:
            click.echo(f"  [--] {tool_name} — not installed")
```

Note: debug tools use `[--]` not `[!!]` because they're optional — not having them is not a failure.

**Step 4: Run all tests**

Run: `pytest tests/ -v`
Expected: all pass

**Step 5: Commit**

```bash
git add edesto_dev/cli.py tests/test_cli.py
git commit -m "feat: show debug tool status in edesto doctor"
```

---

### Task 8: Verify all placeholder and integration tests pass

**Files:**
- Modify: `tests/test_templates.py` (if needed)

**Step 1: Run the full test suite**

Run: `pytest tests/ -v`

**Step 2: Check for unfilled placeholder regressions**

The `test_no_unfilled_placeholders` tests are strict. If any new template content contains literal `{var}` patterns, fix them.

**Step 3: Run integration tests specifically**

Run: `pytest tests/test_cli.py::TestIntegration -v`
Run: `pytest tests/test_cli.py::TestIntegrationMultiToolchain -v`

**Step 4: Manual sanity check — print full output**

```bash
python -c "
from edesto_dev.toolchains.arduino import ArduinoToolchain
from edesto_dev.templates import render_from_toolchain
tc = ArduinoToolchain()
board = tc.get_board('esp32')
print(render_from_toolchain(tc, board, '/dev/ttyUSB0', debug_tools=['saleae', 'openocd', 'scope']))
" | head -200
```

Verify:
- `## Debugging` header with tool guide listing all 4 tools
- `### Serial Output` with the Python snippet
- `### Logic Analyzer` with the Saleae snippet
- `### JTAG/SWD` with the OpenOCD snippet
- `### Oscilloscope` with the SCPI snippet
- Each tool section ends with "ask the user to verify" guidance

**Step 5: Commit if any fixes were needed**

```bash
git add -A
git commit -m "fix: address test regressions from debug tools integration"
```
