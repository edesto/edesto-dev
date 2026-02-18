# Multi-Toolchain Support Design

**Date:** 2026-02-18
**Status:** Approved

## Goal

Make `edesto init` work for any microcontroller by auto-detecting the toolchain from project files and the board from USB, then generating a CLAUDE.md with the right compile/upload/validate commands.

## Core Abstraction: Toolchain

A `Toolchain` ABC that encapsulates everything that varies between build systems:

| Method | Purpose | Example (PlatformIO) |
|---|---|---|
| `detect_project(path)` | Does this directory have my project files? | Check for `platformio.ini` |
| `detect_boards()` | What boards are connected? | `pio device list --json` |
| `doctor()` | Is this toolchain installed and working? | `pio --version` |
| `scaffold(board, path)` | Create a new project | `pio project init --board esp32dev` |
| `compile_command(board)` | Command string for CLAUDE.md | `pio run` |
| `upload_command(board, port)` | Command string for CLAUDE.md | `pio run --target upload --upload-port {port}` |
| `monitor_command(board, port)` | Command string for CLAUDE.md | `pio device monitor --baud 115200` |
| `serial_config(board)` | Baud rate, serial conventions | `{"baud_rate": 115200}` |
| `board_info(board)` | Pins, capabilities, pitfalls | Board-specific metadata |

## Built-in Toolchains (v1)

1. **Arduino** — migrated from current `boards.py`, all 12 board definitions preserved
2. **PlatformIO** — broad board support via `pio`
3. **ESP-IDF** — native Espressif development
4. **MicroPython** — no compile step, file copy + REPL

## Detection Flow

Four-layer detection with fallback chain:

1. **Check for `edesto.toml`** — user-provided or previously saved config takes priority
2. **Scan project files** — match a built-in toolchain:
   - `platformio.ini` → PlatformIO
   - `CMakeLists.txt` + `sdkconfig` or `idf_component_register` → ESP-IDF
   - `*.ino` → Arduino
   - `boot.py` / `main.py` (MicroPython structure) → MicroPython
   - Priority when multiple match: edesto.toml > PlatformIO > ESP-IDF > Arduino > MicroPython
3. **Scan USB** — detect connected board via toolchain-specific detection + USB VID/PID
4. **Nothing works** — ask user for compile/upload commands, save to `edesto.toml`

### Board Detection (Two Layers)

- **Layer 1: Toolchain-specific** — each toolchain has its own board detection (e.g., `arduino-cli board list`, `pio device list`)
- **Layer 2: USB VID/PID fallback** — known vendor IDs identify board families (ST-Link 0x0483 → STM32, Espressif 0x303A → ESP32-S3, etc.)

### Scaffolding for New Projects

When no project files exist:

1. Detect board from USB
2. Ask user which toolchain to use (recommend based on detected board + installed tools)
3. Delegate scaffolding to the toolchain's own CLI:
   - Arduino: `arduino-cli sketch new`
   - PlatformIO: `pio project init --board <board>`
   - ESP-IDF: `idf.py create-project`
   - MicroPython: create `boot.py` + `main.py`
4. Generate CLAUDE.md

### Custom Toolchain Fallback (edesto.toml)

When edesto can't detect the toolchain, it asks the user:

```
? What command compiles your firmware? make build
? What command uploads to the board? make flash PORT=/dev/cu.usbserial-110
? What baud rate does your board use? 115200
```

Saved to `edesto.toml`:

```toml
[toolchain]
name = "custom"
compile = "make build"
upload = "make flash PORT={port}"

[serial]
baud_rate = 115200
port = "/dev/cu.usbserial-110"
```

This file also serves as an override — users can manually create it to customize commands for any toolchain.

## Generic CLAUDE.md Template

The template becomes toolchain-agnostic:

```markdown
# CLAUDE.md — {board_name} ({toolchain_name})

## Hardware
- Board: {board_name}
- Port: {port}
- Baud rate: {baud_rate}

## Commands
- Compile: `{compile_command}`
- Upload: `{upload_command}`
- Monitor: `{monitor_command}`

## Development Loop
1. Edit firmware source files
2. Compile: `{compile_command}`
   - If errors, fix and recompile
3. Upload: `{upload_command}`
4. Wait {boot_delay} seconds for board reboot
5. Validate via serial:
{validation_snippet}

## Serial Conventions
- Baud rate: {baud_rate}
- Use complete lines (newline-terminated)
- Print `[READY]` when initialization is complete
- Print `[ERROR] <description>` for errors
- Use tags for structured output: `[SENSOR] key=value`

## Board Reference
{board_specific_info}
```

All placeholders are filled by the toolchain's methods.

## Module Structure

```
edesto_dev/
├── __init__.py
├── cli.py                    # Click CLI (init, doctor, boards) — refactored
├── detect.py                 # NEW: project + USB detection logic
├── templates.py              # Refactored: generic template renderer
├── toolchain.py              # NEW: abstract Toolchain base class
└── toolchains/               # NEW: one module per toolchain
    ├── __init__.py            # Registry: discovers and registers all toolchains
    ├── arduino.py             # Arduino toolchain (migrated from boards.py)
    ├── platformio.py          # PlatformIO toolchain
    ├── espidf.py              # ESP-IDF toolchain
    └── micropython.py         # MicroPython toolchain
```

### File Changes

- `boards.py` → **deleted**. Board definitions move into `toolchains/arduino.py`.
- `cli.py` → **refactored**. Uses `detect.py` for toolchain/board resolution.
- `templates.py` → **simplified**. Generic renderer taking toolchain-provided data.

### New Files

- `toolchain.py` — `Toolchain` ABC with the interface above
- `detect.py` — project file scanning, USB detection, fallback logic
- `toolchains/__init__.py` — toolchain registry
- `toolchains/arduino.py` — Arduino implementation (migrated from boards.py)
- `toolchains/platformio.py` — PlatformIO implementation
- `toolchains/espidf.py` — ESP-IDF implementation
- `toolchains/micropython.py` — MicroPython implementation

## CLI Changes

### `edesto init`

- New `--toolchain` flag for explicit override (e.g., `edesto init --toolchain platformio`)
- Existing `--board` and `--port` flags remain
- If toolchain auto-detected or specified, skip the "which toolchain?" prompt

### `edesto doctor`

- Checks all installed toolchains, not just arduino-cli
- Reports which toolchains are available and which are missing

### `edesto boards`

- Lists boards from all registered toolchains, grouped by toolchain
- New `--toolchain` filter (e.g., `edesto boards --toolchain arduino`)

## What Stays the Same

- Serial validation protocol (`[READY]`, `[ERROR]`, `[SENSOR]`)
- Development loop structure (edit → compile → flash → validate)
- CLI UX (`edesto init`, `edesto doctor`, `edesto boards`)
- Dependencies (click, pyserial)
- Validation method: serial only (for now)

## What Changes

- Arduino is no longer special — it's one of several toolchain implementations
- Template is generic — commands come from the toolchain, not hardcoded
- Board detection is two-layer — USB hardware + toolchain-specific
- New `edesto.toml` for custom/override configuration
- New `--toolchain` flag on CLI commands
