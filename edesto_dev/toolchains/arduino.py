"""Arduino toolchain for edesto-dev."""

import json
import shutil
import subprocess
from pathlib import Path

from edesto_dev.toolchain import Board, DetectedBoard, Toolchain

# VID/PID -> candidate board slugs for USB-serial chips that don't carry board identity.
# Used as a fallback when arduino-cli returns a port with no matching_boards.
_VID_PID_HINTS: dict[tuple[int, int], list[str]] = {
    # CH340 - common on ESP32, ESP8266, Arduino Nano clones
    (0x1A86, 0x7523): ["esp32", "esp8266", "arduino-nano"],
    # CH9102 - newer chip, mostly on ESP32 boards
    (0x1A86, 0x55D4): ["esp32"],
    # CP2102 - common on ESP32 DevKit and some ESP8266
    (0x10C4, 0xEA60): ["esp32", "esp8266"],
}


def _base_fqbn(fqbn: str) -> str:
    """Return the first three colon-separated segments of an FQBN (vendor:arch:board)."""
    parts = fqbn.split(":")
    return ":".join(parts[:3])


def _build_boards() -> dict[str, Board]:
    """Build the dict of all 12 Arduino board definitions."""
    boards: dict[str, Board] = {}

    def _reg(b: Board) -> None:
        boards[b.slug] = b

    # --- ESP32 ---
    _reg(Board(
        slug="esp32",
        name="ESP32",
        fqbn="esp32:esp32:esp32:UploadSpeed=115200",
        core="esp32:esp32",
        core_url="https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json",
        baud_rate=115200,
        openocd_target="esp32",
        capabilities=["wifi", "bluetooth", "ble", "http_server", "ota", "spiffs", "preferences"],
        pins={
            "onboard_led": 2,
            "boot_button": 0,
            "i2c_sda": 21,
            "i2c_scl": 22,
            "spi_mosi": 23,
            "spi_miso": 19,
            "spi_sck": 18,
            "spi_ss": 5,
            "dac1": 25,
            "dac2": 26,
        },
        pin_notes=[
            "GPIO 0: Boot button — do not use for general I/O",
            "GPIO 2: Onboard LED",
            "GPIO 34-39: Input only (no pull-up/pull-down)",
            "ADC1: GPIO 32-39 (12-bit, works alongside WiFi)",
            "ADC2: GPIO 0,2,4,12-15,25-27 (does NOT work when WiFi is active)",
            "DAC: GPIO 25 (DAC1), GPIO 26 (DAC2)",
            "I2C default: SDA=21, SCL=22",
            "SPI default: MOSI=23, MISO=19, SCK=18, SS=5",
        ],
        pitfalls=[
            "ADC2 pins do not work when WiFi is active. Use ADC1 pins (32-39) if you need analog reads with WiFi.",
            "WiFi and Bluetooth at full power simultaneously will cause instability. Use one at a time or reduce power.",
            "If upload fails with 'connection timeout', hold the BOOT button while uploading.",
            "The ESP32 prints boot messages (rst:, boot:) on serial. Ignore these in your validation.",
            "delay() blocks the entire core. Use millis() for non-blocking timing.",
            "Stack size is 8KB per task by default. Use xTaskCreate() with a larger stack for complex tasks.",
            "OTA requires enough free flash for two firmware images. Use a partition scheme that supports this.",
            "String concatenation in loops causes heap fragmentation. Use char[] buffers for repeated operations.",
        ],
        includes={
            "wifi": "#include <WiFi.h>",
            "bluetooth": "#include <BluetoothSerial.h>",
            "http_server": "#include <WebServer.h>",
            "ota": "#include <ArduinoOTA.h>",
            "preferences": "#include <Preferences.h>",
            "spiffs": "#include <SPIFFS.h>",
        },
    ))

    # --- ESP32-S3 ---
    _reg(Board(
        slug="esp32s3",
        name="ESP32-S3",
        fqbn="esp32:esp32:esp32s3:UploadSpeed=115200",
        core="esp32:esp32",
        core_url="https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json",
        baud_rate=115200,
        openocd_target="esp32s3",
        capabilities=["wifi", "ble", "http_server", "ota", "spiffs", "preferences", "usb_native"],
        pins={
            "onboard_led": 48,
            "i2c_sda": 8,
            "i2c_scl": 9,
            "spi_mosi": 11,
            "spi_miso": 13,
            "spi_sck": 12,
            "spi_ss": 10,
        },
        pin_notes=[
            "GPIO 48: RGB LED (WS2812-style, not a simple HIGH/LOW LED)",
            "GPIO 19/20: USB D-/D+ — do not use for general I/O",
            "GPIO 0: Boot button — do not use for general I/O",
            "ADC1: GPIO 1-10 (works alongside WiFi)",
            "ADC2: GPIO 11-20 (does NOT work when WiFi is active)",
            "I2C default: SDA=8, SCL=9",
            "SPI default: MOSI=11, MISO=13, SCK=12, SS=10",
        ],
        pitfalls=[
            "ADC2 pins do not work when WiFi is active. Use ADC1 pins (1-10) if you need analog reads with WiFi.",
            "GPIO 19/20 are USB pins. Do not use them for general I/O.",
            "RGB LED on GPIO 48 requires NeoPixel-style protocol, not simple digitalWrite.",
            "If upload fails, hold BOOT and press RST, then release BOOT after upload starts.",
            "delay() blocks the entire core. Use millis() for non-blocking timing.",
            "String concatenation in loops causes heap fragmentation. Use char[] buffers for repeated operations.",
        ],
        includes={
            "wifi": "#include <WiFi.h>",
            "http_server": "#include <WebServer.h>",
            "ota": "#include <ArduinoOTA.h>",
            "preferences": "#include <Preferences.h>",
            "spiffs": "#include <SPIFFS.h>",
        },
    ))

    # --- ESP32-C3 ---
    _reg(Board(
        slug="esp32c3",
        name="ESP32-C3",
        fqbn="esp32:esp32:esp32c3:UploadSpeed=115200",
        core="esp32:esp32",
        core_url="https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json",
        baud_rate=115200,
        openocd_target="esp32c3",
        capabilities=["wifi", "ble", "http_server", "ota", "spiffs", "preferences"],
        pins={
            "onboard_led": 8,
            "i2c_sda": 8,
            "i2c_scl": 9,
            "spi_mosi": 6,
            "spi_miso": 5,
            "spi_sck": 4,
            "spi_ss": 7,
        },
        pin_notes=[
            "GPIO 8: Onboard LED",
            "GPIO 9: Boot button — do not use for general I/O",
            "Only 22 GPIO pins available",
            "ADC1: GPIO 0-4 (no ADC2 on this chip)",
            "RISC-V single core architecture",
        ],
        pitfalls=[
            "Single-core RISC-V — no dual-core parallelism available.",
            "Only 22 GPIO pins. Plan pin usage carefully.",
            "GPIO 8 is shared between onboard LED and I2C SDA. Use a different SDA pin if LED is needed.",
            "GPIO 9 is the BOOT button. Do not use for general I/O.",
            "delay() blocks the entire core. Use millis() for non-blocking timing.",
            "No Bluetooth Classic — only BLE is supported.",
        ],
        includes={
            "wifi": "#include <WiFi.h>",
            "http_server": "#include <WebServer.h>",
            "ota": "#include <ArduinoOTA.h>",
            "preferences": "#include <Preferences.h>",
            "spiffs": "#include <SPIFFS.h>",
        },
    ))

    # --- ESP32-C6 ---
    _reg(Board(
        slug="esp32c6",
        name="ESP32-C6",
        fqbn="esp32:esp32:esp32c6:UploadSpeed=115200",
        core="esp32:esp32",
        core_url="https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json",
        baud_rate=115200,
        openocd_target="esp32c6",
        capabilities=["wifi", "wifi6", "ble", "zigbee", "thread", "http_server", "ota", "spiffs", "preferences"],
        pins={
            "onboard_led": 8,
            "i2c_sda": 6,
            "i2c_scl": 7,
            "spi_mosi": 19,
            "spi_miso": 20,
            "spi_sck": 21,
            "spi_ss": 18,
        },
        pin_notes=[
            "GPIO 8: Onboard LED",
            "GPIO 9: Boot button — do not use for general I/O",
            "30 GPIO pins available",
            "ADC1: GPIO 0-6",
            "RISC-V architecture",
            "IEEE 802.15.4 radio for Zigbee/Thread",
        ],
        pitfalls=[
            "Single high-performance RISC-V core — no dual-core parallelism.",
            "WiFi 6 support requires ESP-IDF v5.1+ (check your Arduino core version).",
            "Zigbee and Thread share the 802.15.4 radio — cannot use both simultaneously.",
            "GPIO 9 is the BOOT button. Do not use for general I/O.",
            "delay() blocks the entire core. Use millis() for non-blocking timing.",
            "No Bluetooth Classic — only BLE is supported.",
            "Newer chip — verify your Arduino ESP32 core version supports it.",
        ],
        includes={
            "wifi": "#include <WiFi.h>",
            "http_server": "#include <WebServer.h>",
            "ota": "#include <ArduinoOTA.h>",
            "preferences": "#include <Preferences.h>",
            "spiffs": "#include <SPIFFS.h>",
        },
    ))

    # --- ESP8266 ---
    _reg(Board(
        slug="esp8266",
        name="ESP8266",
        fqbn="esp8266:esp8266:nodemcuv2",
        core="esp8266:esp8266",
        core_url="https://arduino.esp8266.com/stable/package_esp8266com_index.json",
        baud_rate=115200,
        capabilities=["wifi", "http_server", "ota", "spiffs"],
        pins={
            "onboard_led": 2,
            "i2c_sda": 4,
            "i2c_scl": 5,
            "spi_mosi": 13,
            "spi_miso": 12,
            "spi_sck": 14,
            "spi_ss": 15,
        },
        pin_notes=[
            "GPIO 2: Onboard LED (active LOW — LOW turns it ON)",
            "GPIO 0: Flash/boot mode — do not use for general I/O",
            "GPIO 16: Deep sleep wake — connect to RST for deep sleep wake-up",
            "1 ADC pin (A0), 10-bit resolution, 0-1V range",
            "I2C default: SDA=4 (D2), SCL=5 (D1)",
            "NodeMCU D-labels differ from GPIO numbers (D1=GPIO5, D2=GPIO4, etc.)",
        ],
        pitfalls=[
            "Only 80KB RAM — avoid large buffers and dynamic memory allocation.",
            "Single core — delay() blocks WiFi stack. Use yield() or millis()-based timing.",
            "GPIO 6-11 are connected to flash. Do not use them.",
            "Onboard LED is active LOW — digitalWrite(2, LOW) turns it ON.",
            "ADC range is 0-1V (not 3.3V). Use a voltage divider for higher voltages.",
            "Watchdog timer will reset the chip if loop() takes too long. Use yield() in long operations.",
            "2.4GHz WiFi only — no 5GHz support.",
        ],
        includes={
            "wifi": "#include <ESP8266WiFi.h>",
            "http_server": "#include <ESP8266WebServer.h>",
            "ota": "#include <ArduinoOTA.h>",
            "spiffs": "#include <FS.h>",
        },
    ))

    # --- Arduino Uno ---
    _reg(Board(
        slug="arduino-uno",
        name="Arduino Uno",
        fqbn="arduino:avr:uno",
        core="arduino:avr",
        core_url="",
        baud_rate=9600,
        capabilities=["digital_io", "analog_input", "pwm", "i2c", "spi", "uart"],
        pins={
            "onboard_led": 13,
            "i2c_sda": 18,
            "i2c_scl": 19,
            "spi_mosi": 11,
            "spi_miso": 12,
            "spi_sck": 13,
            "spi_ss": 10,
        },
        pin_notes=[
            "GPIO 13: Onboard LED (shared with SPI SCK)",
            "A0-A5: 10-bit analog input",
            "PWM: pins 3, 5, 6, 9, 10, 11",
            "I2C: SDA=A4, SCL=A5",
            "Pin 13 flickers during SPI communication",
            "Pins 0/1: Serial TX/RX (shared with USB)",
        ],
        pitfalls=[
            "Only 2KB SRAM and 32KB flash. Avoid String objects and large arrays.",
            "No floating-point hardware — float operations are slow and use flash.",
            "Pin 13 is shared with SPI SCK. LED flickers during SPI communication.",
            "Pins 0/1 are shared with USB serial. Do not use for I/O during serial communication.",
            "analogWrite() is PWM, not true analog output. No DAC available.",
            "External interrupts only on pins 2 and 3.",
            "delay() blocks the entire MCU. Use millis() for non-blocking timing.",
            "No WiFi or Bluetooth. Use external modules (ESP-01, HC-05) if needed.",
        ],
        includes={},
    ))

    # --- Arduino Nano ---
    _reg(Board(
        slug="arduino-nano",
        name="Arduino Nano",
        fqbn="arduino:avr:nano",
        core="arduino:avr",
        core_url="",
        baud_rate=9600,
        capabilities=["digital_io", "analog_input", "pwm", "i2c", "spi", "uart"],
        pins={
            "onboard_led": 13,
            "i2c_sda": 18,
            "i2c_scl": 19,
            "spi_mosi": 11,
            "spi_miso": 12,
            "spi_sck": 13,
            "spi_ss": 10,
        },
        pin_notes=[
            "GPIO 13: Onboard LED",
            "A0-A7: analog input (A6/A7 are analog input only, no digital)",
            "PWM: pins 3, 5, 6, 9, 10, 11",
            "I2C: SDA=A4, SCL=A5",
            "Pins 0/1: Serial TX/RX (shared with USB)",
        ],
        pitfalls=[
            "Only 2KB SRAM and 32KB flash. Avoid String objects and large arrays.",
            "A6/A7 are analog input only — cannot be used as digital I/O.",
            "Clone Nanos often need old bootloader: use --fqbn arduino:avr:nano:cpu=atmega328old.",
            "No floating-point hardware — float operations are slow and use flash.",
            "Pins 0/1 are shared with USB serial. Do not use for I/O during serial communication.",
            "External interrupts only on pins 2 and 3.",
            "delay() blocks the entire MCU. Use millis() for non-blocking timing.",
            "No WiFi or Bluetooth. Use external modules if needed.",
        ],
        includes={},
    ))

    # --- Arduino Mega 2560 ---
    _reg(Board(
        slug="arduino-mega",
        name="Arduino Mega 2560",
        fqbn="arduino:avr:mega",
        core="arduino:avr",
        core_url="",
        baud_rate=9600,
        capabilities=["digital_io", "analog_input", "pwm", "i2c", "spi", "uart", "multi_serial"],
        pins={
            "onboard_led": 13,
            "i2c_sda": 20,
            "i2c_scl": 21,
            "spi_mosi": 51,
            "spi_miso": 50,
            "spi_sck": 52,
            "spi_ss": 53,
        },
        pin_notes=[
            "GPIO 13: Onboard LED",
            "A0-A15: 16 analog input channels, 10-bit",
            "PWM: pins 2-13, 44-46",
            "I2C: SDA=20, SCL=21",
            "SPI: MOSI=51, MISO=50, SCK=52, SS=53",
            "4 serial ports: Serial (0/1), Serial1 (18/19), Serial2 (16/17), Serial3 (14/15)",
            "External interrupts: pins 2, 3, 18, 19, 20, 21",
        ],
        pitfalls=[
            "8KB SRAM and 256KB flash — more than Uno but still limited.",
            "No floating-point hardware — float operations are slow.",
            "SPI is on pins 50-53, NOT 11-13 like Uno. Code from Uno examples must be adapted.",
            "Pin 53 (SS) must be set as OUTPUT even if not used, or SPI will not work.",
            "analogWrite() is PWM, not true analog output. No DAC available.",
            "delay() blocks the entire MCU. Use millis() for non-blocking timing.",
            "No WiFi or Bluetooth. Use external modules if needed.",
        ],
        includes={},
    ))

    # --- Raspberry Pi Pico (RP2040) ---
    _reg(Board(
        slug="rp2040",
        name="Raspberry Pi Pico (RP2040)",
        fqbn="rp2040:rp2040:rpipico",
        core="rp2040:rp2040",
        core_url="https://github.com/earlephilhower/arduino-pico/releases/download/global/package_rp2040_index.json",
        baud_rate=115200,
        openocd_target="rp2040",
        capabilities=["digital_io", "analog_input", "pwm", "i2c", "spi", "uart", "pio", "dual_core", "usb_native"],
        pins={
            "onboard_led": 25,
            "i2c_sda": 4,
            "i2c_scl": 5,
            "spi_mosi": 19,
            "spi_miso": 16,
            "spi_sck": 18,
            "spi_ss": 17,
        },
        pin_notes=[
            "GPIO 25: Onboard LED",
            "ADC: GPIO 26-28 (12-bit) + GPIO 29 (VSYS/3 voltage monitor)",
            "All GPIO pins support PWM",
            "I2C0: SDA=4, SCL=5 | I2C1: SDA=6, SCL=7",
            "SPI0: MOSI=19, MISO=16, SCK=18, SS=17 | SPI1: MOSI=15, MISO=12, SCK=14, SS=13",
            "UART0: TX=0, RX=1 | UART1: TX=8, RX=9",
            "2 PIO (Programmable I/O) blocks for custom protocols",
        ],
        pitfalls=[
            "264KB SRAM and 2MB flash. Adequate for most projects but plan large buffers carefully.",
            "First upload requires BOOTSEL mode — hold BOOTSEL while plugging in USB.",
            "Pico W has LED on different pin (via CYW43 WiFi chip). This definition is for Pico (non-W).",
            "ADC has known offset error. Calibrate if precision is needed.",
            "USB Serial is separate from UART. Serial is USB, Serial1/Serial2 are UART.",
            "No EEPROM — use LittleFS for persistent storage.",
            "delay() only blocks the current core. Use millis() for non-blocking timing.",
            "Dual core: use setup1()/loop1() for second core tasks.",
        ],
        includes={},
    ))

    # --- Teensy 4.0 ---
    _reg(Board(
        slug="teensy40",
        name="Teensy 4.0",
        fqbn="teensy:avr:teensy40",
        core="teensy:avr",
        core_url="https://www.pjrc.com/teensy/package_teensy_index.json",
        baud_rate=115200,
        capabilities=["digital_io", "analog_input", "pwm", "i2c", "spi", "uart", "usb_native", "audio", "can_bus"],
        pins={
            "onboard_led": 13,
            "i2c_sda": 18,
            "i2c_scl": 19,
            "spi_mosi": 11,
            "spi_miso": 12,
            "spi_sck": 13,
            "spi_ss": 10,
        },
        pin_notes=[
            "GPIO 13: Onboard LED",
            "14 ADC pins, 12-bit resolution",
            "PWM on many pins",
            "3 I2C buses",
            "2 SPI buses",
            "7 UART serial ports",
            "CAN bus support",
            "Native USB",
        ],
        pitfalls=[
            "Upload uses teensy_loader_cli, not standard serial upload.",
            "USB CDC — baud rate setting is ignored (always full USB speed).",
            "600MHz ARM Cortex-M7 runs hot. Consider heat management for sustained loads.",
            "1024KB flash, 512KB RAM — generous but not unlimited.",
            "No WiFi or Bluetooth. Use external modules if needed.",
            "Program button for bootloader mode.",
            "Use analogReadResolution(12) to get full 12-bit ADC resolution.",
            "Use elapsedMillis/elapsedMicros for non-blocking timing.",
        ],
        includes={},
    ))

    # --- Teensy 4.1 ---
    _reg(Board(
        slug="teensy41",
        name="Teensy 4.1",
        fqbn="teensy:avr:teensy41",
        core="teensy:avr",
        core_url="https://www.pjrc.com/teensy/package_teensy_index.json",
        baud_rate=115200,
        capabilities=["digital_io", "analog_input", "pwm", "i2c", "spi", "uart", "usb_native", "audio", "can_bus", "ethernet", "sd_card"],
        pins={
            "onboard_led": 13,
            "i2c_sda": 18,
            "i2c_scl": 19,
            "spi_mosi": 11,
            "spi_miso": 12,
            "spi_sck": 13,
            "spi_ss": 10,
        },
        pin_notes=[
            "GPIO 13: Onboard LED",
            "18 ADC pins",
            "PWM on many pins",
            "3 I2C buses",
            "2 SPI buses",
            "8 UART serial ports",
            "Native Ethernet (requires MagJack soldering)",
            "SD card via SDIO (bottom side)",
            "USB host support",
            "Optional PSRAM (solder pads on bottom)",
        ],
        pitfalls=[
            "Upload uses teensy_loader_cli, not standard serial upload.",
            "USB CDC — baud rate setting is ignored (always full USB speed).",
            "Ethernet requires soldering a MagJack connector to the board.",
            "SD card slot is on the bottom — use BUILTIN_SDCARD constant.",
            "PSRAM uses EXTMEM keyword for allocation.",
            "8MB flash — much more than Teensy 4.0.",
            "Program button for bootloader mode.",
            "Use elapsedMillis/elapsedMicros for non-blocking timing.",
        ],
        includes={},
    ))

    # --- STM32 Nucleo-64 ---
    _reg(Board(
        slug="stm32-nucleo",
        name="STM32 Nucleo-64",
        fqbn="STMicroelectronics:stm32:Nucleo_64",
        core="STMicroelectronics:stm32",
        core_url="https://github.com/stm32duino/BoardManagerFiles/raw/main/package_stmicroelectronics_index.json",
        baud_rate=115200,
        openocd_target="stm32f4x",
        capabilities=["digital_io", "analog_input", "pwm", "i2c", "spi", "uart", "dac", "can_bus"],
        pins={
            "onboard_led": 13,
            "i2c_sda": 14,
            "i2c_scl": 15,
            "spi_mosi": 11,
            "spi_miso": 12,
            "spi_sck": 13,
            "spi_ss": 10,
        },
        pin_notes=[
            "LD2 on PA5/D13",
            "B1 user button on PC13",
            "Arduino-compatible headers: D0-D15, A0-A5",
            "ADC: 12-bit resolution",
            "DAC available on some variants",
            "I2C: D14 (SDA), D15 (SCL)",
            "SPI: D11 (MOSI), D12 (MISO), D13 (SCK)",
            "UART via ST-Link Virtual COM Port (VCP)",
        ],
        pitfalls=[
            "Nucleo-64 is a family — many chip variants exist. Verify your specific board variant.",
            "Upload is via ST-Link, not USB serial. Install ST-Link drivers.",
            "Serial output is via ST-Link VCP, not native USB serial.",
            "Arduino pin mapping differs from STM32 native pin names (PA0, PB3, etc.).",
            "Library compatibility varies — not all Arduino libraries work with STM32.",
            "Flash and RAM sizes vary by chip variant.",
            "ST-Link drivers required on Windows.",
            "delay() blocks. Use millis() or HAL_GetTick() for non-blocking timing.",
        ],
        includes={},
    ))

    return boards


class ArduinoToolchain(Toolchain):
    """Arduino toolchain using arduino-cli."""

    def __init__(self) -> None:
        self._boards = _build_boards()

    # -- Toolchain interface --------------------------------------------------

    @property
    def name(self) -> str:
        return "arduino"

    def list_boards(self) -> list[Board]:
        """Return all supported Arduino boards."""
        return list(self._boards.values())

    def get_board(self, slug: str) -> Board | None:
        """Look up a board by slug (O(1) dict lookup)."""
        return self._boards.get(slug)

    def detect_project(self, path: Path) -> bool:
        """Return True if any .ino file exists in the directory."""
        return any(path.glob("*.ino"))

    def detect_boards(self) -> list[DetectedBoard]:
        """Detect connected boards via arduino-cli. Returns empty list on failure."""
        try:
            result = subprocess.run(
                ["arduino-cli", "board", "list", "--format", "json"],
                capture_output=True, text=True, timeout=10,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return []

        if result.returncode != 0:
            return []

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return []

        detected: list[DetectedBoard] = []
        for entry in data.get("detected_ports", []):
            port_info = entry.get("port", {})
            port = port_info.get("address", "")
            if not port:
                continue

            # Try FQBN matching first (takes priority)
            fqbn_matched = False
            for match in entry.get("matching_boards", []):
                fqbn = match.get("fqbn", "")
                board = self._get_board_by_fqbn(fqbn)
                if board:
                    detected.append(DetectedBoard(board=board, port=port, toolchain_name="arduino"))
                    fqbn_matched = True

            # VID/PID fallback for generic USB-serial chips
            if not fqbn_matched:
                props = port_info.get("properties", {})
                vid = props.get("vid", "")
                pid = props.get("pid", "")
                if vid and pid:
                    try:
                        key = (int(vid, 16), int(pid, 16))
                    except ValueError:
                        continue
                    for slug in _VID_PID_HINTS.get(key, []):
                        board = self._boards.get(slug)
                        if board:
                            detected.append(DetectedBoard(board=board, port=port, toolchain_name="arduino"))

        return detected

    def compile_command(self, board: Board) -> str:
        """Return the arduino-cli compile command."""
        return f"arduino-cli compile --fqbn {board.fqbn} ."

    def upload_command(self, board: Board, port: str) -> str:
        """Return the arduino-cli upload command."""
        return f"arduino-cli upload --fqbn {board.fqbn} --port {port} ."

    def monitor_command(self, board: Board, port: str) -> str:
        """Return the arduino-cli monitor command."""
        return f"arduino-cli monitor --port {port} --config baudrate={board.baud_rate}"

    def serial_config(self, board: Board) -> dict:
        """Return serial configuration for the board."""
        return {"baud_rate": board.baud_rate, "boot_delay": 3}

    def setup_info(self, board: Board) -> str | None:
        """Return arduino-cli core install command."""
        if board.core_url:
            return f"arduino-cli core install {board.core} --additional-urls {board.core_url}"
        elif board.core:
            return f"arduino-cli core install {board.core}"
        return None

    def board_info(self, board: Board) -> dict:
        """Return board-specific info for the template."""
        return {
            "capabilities": board.capabilities,
            "pins": board.pins,
            "pitfalls": board.pitfalls,
            "pin_notes": board.pin_notes,
            "includes": board.includes,
        }

    def doctor(self) -> dict:
        """Check if arduino-cli is installed."""
        path = shutil.which("arduino-cli")
        if path:
            return {"ok": True, "message": f"arduino-cli found at {path}"}
        return {"ok": False, "message": "arduino-cli not found. Install from https://arduino.github.io/arduino-cli/"}

    def scaffold(self, board: Board, path: Path) -> None:
        """Create a new Arduino sketch via arduino-cli sketch new."""
        subprocess.run(
            ["arduino-cli", "sketch", "new", str(path)],
            check=True,
        )

    # -- Private helpers ------------------------------------------------------

    def _get_board_by_fqbn(self, fqbn: str) -> Board | None:
        """Find a board by its FQBN. Matches on the base vendor:arch:board portion."""
        target = _base_fqbn(fqbn)
        for board in self._boards.values():
            if _base_fqbn(board.fqbn) == target:
                return board
        return None


# Auto-register this toolchain when the module is imported.
from edesto_dev.toolchains import register_toolchain  # noqa: E402

register_toolchain(ArduinoToolchain())
