# JTAG Upload Method for `edesto init`

## Problem

`edesto init` only detects boards via USB serial. Boards connected through JTAG debuggers (ST-Link, J-Link, CMSIS-DAP) are invisible — the user falls into the manual custom toolchain flow and loses all board-specific knowledge.

## Decision: JTAG as an upload method, not a toolchain

JTAG replaces *how you flash*, not *how you compile*. An STM32 Nucleo flashed via ST-Link still compiles with Arduino. The compile/upload split already exists in the `Toolchain` interface — we make the upload swappable.

## Data Model

New dataclass in `toolchain.py`:

```python
@dataclass
class JtagConfig:
    interface: str   # OpenOCD interface config name: "stlink", "jlink", "cmsis-dap"
    target: str      # OpenOCD target config name: "stm32f4x", "nrf52", "esp32", "rp2040"
```

## CLI Changes

### New flag

`--upload jtag` on `edesto init`. Forces the JTAG setup path regardless of USB detection.

### Auto-fallback

When no USB serial boards are found AND OpenOCD is installed, offer:

```
No boards detected via USB serial.
OpenOCD is installed — set up for JTAG/SWD flashing? [Y/n]
```

If yes → enter JTAG setup flow. If no → fall through to existing custom toolchain flow.

### JTAG setup prompts

1. Pick a board (from existing board list across all toolchains, or "custom")
2. Pick a toolchain for compilation (if not auto-detected from project files)
3. Pick debug probe: ST-Link / J-Link / CMSIS-DAP / Other (prompt for config name)
4. Pick target chip config (default inferred from board — e.g. `stm32-nucleo` → `stm32f4x.cfg`)
5. "Do you have a serial port for monitoring?" → if yes, prompt for port; if no, skip serial config

### Board-to-target mapping

Boards in `arduino.py` get an optional `openocd_target` field:

| Board slug    | Default OpenOCD target |
|---------------|----------------------|
| stm32-nucleo  | stm32f4x             |
| esp32         | esp32                |
| esp32s3       | esp32s3              |
| esp32c3       | esp32c3              |
| esp32c6       | esp32c6              |
| rp2040        | rp2040               |
| teensy40      | (none — uses teensy_loader) |
| teensy41      | (none — uses teensy_loader) |
| arduino-uno   | (none — no JTAG)     |
| arduino-nano  | (none — no JTAG)     |
| arduino-mega  | (none — no JTAG)     |

## Template Changes

### Header

When JTAG is configured:

```markdown
You are developing firmware for a STM32 Nucleo-64 connected via JTAG/SWD.

## Hardware
- Board: STM32 Nucleo-64
- Debug probe: ST-Link
- Framework: Arduino
- Upload: openocd (JTAG/SWD)
- Serial port: /dev/cu.usbmodem1103 (or "none — use JTAG debugging")
```

### Upload command

One-shot OpenOCD invocation:

```
openocd -f interface/stlink.cfg -f target/stm32f4x.cfg \
  -c "program build/firmware.elf verify reset exit"
```

The ELF path depends on the toolchain's build output location.

### Serial section

Conditional — only included if the user provided a serial port. If no serial port, the debugging section emphasizes JTAG/SWD methods.

### OpenOCD in debug tools

Always force `"openocd"` into the debug_tools list for JTAG setups (we know it's installed).

## edesto.toml

JTAG config is persisted so re-running `edesto init` can reload it:

```toml
[jtag]
interface = "stlink"
target = "stm32f4x"
```

## What stays the same

- Board definitions (capabilities, pins, pitfalls)
- Toolchain compile commands
- `Toolchain` abstract interface
- Existing USB serial detection path
- All other toolchains (PlatformIO, ESP-IDF, MicroPython)
