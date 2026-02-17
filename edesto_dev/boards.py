"""Board definitions for edesto-dev."""

from dataclasses import dataclass, field


class BoardNotFoundError(Exception):
    """Raised when a board slug is not found."""
    pass


@dataclass
class Board:
    slug: str
    name: str
    fqbn: str
    core: str
    core_url: str
    baud_rate: int
    capabilities: list[str] = field(default_factory=list)
    pins: dict[str, int] = field(default_factory=dict)
    pitfalls: list[str] = field(default_factory=list)
    pin_notes: list[str] = field(default_factory=list)
    includes: dict[str, str] = field(default_factory=dict)


BOARDS: dict[str, Board] = {}


def _register(board: Board) -> Board:
    BOARDS[board.slug] = board
    return board


def get_board(slug: str) -> Board:
    """Get a board by its slug. Raises BoardNotFoundError if not found."""
    if slug not in BOARDS:
        raise BoardNotFoundError(f"Unknown board: {slug}. Use 'edesto boards' to list supported boards.")
    return BOARDS[slug]


def list_boards() -> list[Board]:
    """Return all supported boards."""
    return list(BOARDS.values())


# --- ESP32 ---

_register(Board(
    slug="esp32",
    name="ESP32",
    fqbn="esp32:esp32:esp32",
    core="esp32:esp32",
    core_url="https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json",
    baud_rate=115200,
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
