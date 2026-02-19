# edesto-dev

Join our [Discord](https://discord.gg/3bu98EcdAC)

**Teach AI coding agents how to compile, flash, and validate firmware on your hardware.**

AI coding agents stop at the terminal. `edesto init` gives them the full embedded development loop: compile, flash, on-device debugging, iterate. Now they can autonomously develop and debug firmware on real hardware. Works with Claude Code, Cursor, Codex, and OpenClaw.


https://github.com/user-attachments/assets/f1d4719d-ed60-406e-a274-0b0f2b06ac21



## Install

```
pip install edesto-dev
```

## Quick Start

```bash
# 1. Plug in your board and run:
edesto init

# 2. Open your AI coding agent in the same directory
claude

# 3. Tell it what to do:
# "The sensor readings are wrong. Find and fix the bug."
```

That's it. `edesto init` auto-detects your board, serial port, and toolchain. It generates a `SKILLS.md` that teaches your agent the write/compile/flash/validate loop, with board-specific pin references, pitfalls, and serial conventions.

You can also specify everything manually:

```bash
edesto init --board esp32 --port /dev/cu.usbserial-0001
edesto init --board esp32 --port /dev/ttyUSB0 --toolchain arduino
```

### JTAG/SWD Flashing

If your board is connected through a JTAG debugger (ST-Link, J-Link, CMSIS-DAP) instead of USB serial:

```bash
edesto init --board stm32-nucleo --upload jtag
```

This walks you through selecting your debug probe and target chip, generates an OpenOCD-based flash command, and optionally configures a serial port for monitoring. If you run `edesto init` with no USB boards detected and OpenOCD installed, it will offer JTAG setup automatically.

## How It Works

`edesto init` detects your project and generates a `SKILLS.md` (plus copies as `CLAUDE.md`, `.cursorrules`, and `AGENTS.md`) that gives your AI agent:

1. **Compile** and **flash** commands for your specific toolchain
2. A **debugging toolkit** — serial output reading, plus auto-detected support for logic analyzers, JTAG/SWD, and oscilloscopes
3. **Board-specific** pin references, capabilities, and common pitfalls
4. **Datasheet intelligence** — guidance on finding, reading, and citing datasheets and reference manuals, with board-family-specific tips for STM32, ESP32, and Nordic nRF documentation
5. **Troubleshooting** guidance for common failures (port busy, baud mismatch, upload timeout)

The debugging step is what makes this work. For example, your firmware prints structured serial output (`[READY]`, `[ERROR]`, `[SENSOR] key=value`) and the agent reads it to verify its own changes on real hardware. When you have additional debug tools installed, the agent can also drive them programmatically.

## Supported Toolchains

| Toolchain | Detection | Commands |
|-----------|-----------|----------|
| Arduino | `.ino` files | `arduino-cli compile`, `arduino-cli upload` |
| PlatformIO | `platformio.ini` | `pio run`, `pio run --target upload` |
| ESP-IDF | `CMakeLists.txt` + `sdkconfig` | `idf.py build`, `idf.py flash` |
| Zephyr RTOS | `prj.conf`, `west.yml`, or CMake with `find_package(Zephyr` | `west build`, `west flash` |
| CMake/Make (bare-metal) | `Makefile` with cross-compiler or `CMakeLists.txt` with toolchain file | `cmake --build build`, OpenOCD flash |
| MicroPython | `boot.py` / `main.py` | `mpremote connect`, `mpremote cp` |
| Custom | `edesto.toml` | Your commands |

If edesto can't detect your toolchain, it prompts you to enter compile/upload commands and saves them to `edesto.toml` for next time.

## Supported Boards

| Slug | Board | Key Features |
|------|-------|-------------|
| `esp32` | ESP32 | WiFi, Bluetooth, BLE |
| `esp32s3` | ESP32-S3 | WiFi, BLE, USB native |
| `esp32c3` | ESP32-C3 | WiFi, BLE, RISC-V |
| `esp32c6` | ESP32-C6 | WiFi 6, BLE, Zigbee/Thread |
| `esp8266` | ESP8266 | WiFi |
| `arduino-uno` | Arduino Uno | AVR, 32KB flash |
| `arduino-nano` | Arduino Nano | AVR, compact |
| `arduino-mega` | Arduino Mega 2560 | AVR, 256KB flash, 4 serial |
| `rp2040` | Raspberry Pi Pico | Dual-core, PIO, USB |
| `teensy40` | Teensy 4.0 | 600MHz Cortex-M7, USB |
| `teensy41` | Teensy 4.1 | 600MHz, Ethernet, SD card |
| `stm32-nucleo` | STM32 Nucleo-64 | STM32, Arduino headers |
| `stm32f4-discovery` | STM32F4 Discovery | STM32F407, USB OTG, accelerometer, DAC |
| `stm32h7-nucleo` | STM32H7 Nucleo-144 | Dual-core 480MHz, Ethernet |
| `stm32l4-nucleo` | STM32L4 Nucleo-64 | Ultra-low-power, DAC |
| `nrf52840` | Adafruit Feather nRF52840 | BLE 5.0, USB, NFC, QSPI |
| `nrf5340` | nRF5340 DK | Dual-core, BLE 5.3, TrustZone |

Any board works with PlatformIO, ESP-IDF, Zephyr, MicroPython, or a custom toolchain — the table above is for auto-detection with board-specific pin references and pitfalls. Run `edesto boards` to see the full list.

## Debug Tools (Optional)

edesto auto-detects debug tools on your machine and includes them in the generated SKILLS.md. The agent picks the right tool for the problem:

| Tool | What it checks | Detection |
|------|---------------|-----------|
| **Serial output** | Application behavior (always included) | `pyserial` |
| **Logic analyzer** | SPI/I2C/UART protocol timing and bus decoding | [Saleae Logic 2](https://www.saleae.com/) + `logic2-automation` Python package |
| **JTAG/SWD** | CPU state, crashes, HardFaults, registers, memory | `openocd` on PATH |
| **Oscilloscope** | Voltage levels, PWM frequency/duty, rise times | SCPI scope + `pyvisa` Python package |

If a tool isn't installed, its section is simply omitted — the agent won't try to use it. Run `edesto doctor` to see which tools are detected.

## Commands

```bash
edesto init                                     # Auto-detect everything
edesto init --board esp32                       # Specify board, auto-detect port
edesto init --board esp32 --port /dev/ttyUSB0   # Fully manual
edesto init --board stm32-nucleo --upload jtag  # Flash via JTAG/SWD
edesto init --toolchain platformio              # Force a specific toolchain
edesto boards                                   # List supported boards
edesto boards --toolchain arduino               # Filter by toolchain
edesto doctor                                   # Check your environment
```

## Examples

Three example projects in `examples/`, each with an intentional bug for your AI agent to find and fix:

- **sensor-debug** — Temperature sensor with a unit conversion bug. Celsius values are correct but Fahrenheit readings are off.
- **wifi-endpoint** — ESP32 HTTP server where `/health` returns JSON with the wrong Content-Type header.
- **ota-update** — ESP32 with OTA support. The agent updates the version string and pushes firmware wirelessly.

## Prerequisites

- A supported board connected via USB or JTAG debugger
- Python 3.10+
- Your toolchain's CLI installed (e.g., `arduino-cli`, `pio`, `idf.py`, `west`, `arm-none-eabi-gcc`, `mpremote`)
- For JTAG flashing: `openocd` on PATH
- Optional: debug tools (`logic2-automation`, `openocd`, `pyvisa`) for advanced debugging

Run `edesto doctor` to check your setup.

## About

Built by [Edesto](https://edesto.com). We build tools for robotics and embedded teams.
