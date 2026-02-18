# Debug Tools: Logic Analyzer, JTAG/SWD, Oscilloscope

**Date:** 2026-02-18
**Status:** Approved

## Goal

Extend edesto's SKILLS.md to teach AI agents how to use logic analyzers (Saleae), JTAG/SWD debuggers (OpenOCD), and oscilloscopes (SCPI) as equal peers alongside serial output.

## Motivation

Serial output only covers application-level behavior. Embedded developers also need:
- **Protocol debugging** — decode SPI/I2C/UART bus traffic with a logic analyzer
- **CPU-level debugging** — inspect crashes, HardFaults, registers, memory with JTAG/SWD
- **Electrical debugging** — verify PWM frequency, voltage levels, signal timing with an oscilloscope

AI agents can programmatically drive all three: Saleae has a Python automation API, OpenOCD has a TCL RPC port, and oscilloscopes speak SCPI over PyVISA.

## Approach

**Template sections with Python snippets** — same pattern as serial today. Each detected tool gets a section in SKILLS.md with a ready-to-use Python snippet, guidance on when to use it, and conventions for interpreting results.

No new ABC or plugin system. Detection is a simple function that checks for installed packages/binaries. Template sections are conditionally included based on detection results.

## SKILLS.md Structure

The current "## Validation" section becomes "## Debugging" with subsections per tool:

```
## Debugging

Use the right tool for the problem:
- **Serial output** — application-level behavior (sensor readings, state machines, error messages)
- **Logic analyzer** — protocol-level issues (SPI/I2C timing, signal integrity, bus decoding)
- **JTAG/SWD** — CPU-level issues (crashes, HardFaults, register/memory state, breakpoints)
- **Oscilloscope** — electrical issues (voltage levels, PWM frequency/duty, rise times, noise)

### Serial Output
[always present — existing serial snippet]

### Logic Analyzer
[only when Saleae detected]

### JTAG/SWD
[only when OpenOCD detected]

### Oscilloscope
[only when SCPI/pyvisa detected]
```

The Development Loop step 6 changes to: "Validate your changes using the debugging methods below. Pick the right tool for what you're checking."

## Detection

| Tool | Check | What it means |
|------|-------|---------------|
| Saleae | `import saleae` succeeds | `logic2-automation` Python package installed |
| OpenOCD | `shutil.which("openocd")` | `openocd` binary on PATH |
| Oscilloscope | `import pyvisa` succeeds | `pyvisa` Python package installed |

Detection runs during `edesto init` and `edesto doctor`. Results are passed to the template as a list of detected tool names (e.g., `["saleae", "openocd", "scope"]`).

If a tool is not detected, its section is omitted entirely. The agent should never attempt to use a tool that doesn't have a section in the file.

## Snippet Content

### Saleae Logic Analyzer

The snippet:
- Connects to Logic 2 via `Manager.connect()` on port 10430
- Captures N digital channels for a timed duration
- Optionally adds a protocol analyzer (SPI, I2C, UART) and exports decoded data as CSV
- Prints decoded frames for the agent to parse

Guidance: "Use this when you need to verify protocol timing, decode SPI/I2C/UART bus traffic, or check signal edges."

### OpenOCD (JTAG/SWD)

The snippet:
- Connects via TCL RPC port (6666) using a socket helper class
- Halts the CPU, reads registers (PC, SP, LR)
- Reads Cortex-M fault registers (CFSR, HFSR) with bit decoding
- Reads/writes memory at specific addresses
- Can flash firmware as an alternative to the toolchain's upload command

Guidance: "Use this when the board crashes, stops responding, or you need to inspect CPU state. Also use this to read peripheral registers directly."

### Oscilloscope (SCPI)

The snippet:
- Connects via PyVISA (auto-detect resource string)
- Configures trigger and timebase
- Reads measurements: frequency, duty cycle, Vpp, rise time
- Exports waveform data

Guidance: "Use this when you need to verify PWM output, check voltage levels, or measure signal timing."

## Physical Connection Guidance

Each tool snippet ends with: "If the output looks wrong (no signal, all zeros, garbage data), ask the user to verify that the probe/cable is connected to the correct pin before retrying."

The agent should:
1. Only use tools that have a section in the SKILLS.md (detected tools)
2. Assume cables are connected correctly on first attempt
3. If output looks wrong, ask the user to verify physical connections before continuing
4. Never ask about cable connections proactively at the start

## Implementation Scope

### New files
- `edesto_dev/debug_tools.py` — `detect_debug_tools() -> list[str]` function

### Modified files
- `edesto_dev/templates.py` — new `_debugging()` section replaces `_generic_validation()`, conditional subsections for each tool
- `edesto_dev/cli.py` — call `detect_debug_tools()` and pass to template
- `edesto_dev/cli.py` (doctor) — check debug tools in doctor output

### What doesn't change
- Toolchain system
- Board definitions
- Detection system (toolchain/board detection)
- CLI flags
