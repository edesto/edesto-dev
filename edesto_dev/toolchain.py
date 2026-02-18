"""Toolchain abstraction for edesto-dev."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Board:
    """A microcontroller board, independent of any specific toolchain."""
    slug: str
    name: str
    baud_rate: int
    capabilities: list[str] = field(default_factory=list)
    pins: dict[str, int] = field(default_factory=dict)
    pitfalls: list[str] = field(default_factory=list)
    pin_notes: list[str] = field(default_factory=list)
    includes: dict[str, str] = field(default_factory=dict)
    # Toolchain-specific metadata (used by Arduino, ignored by others)
    fqbn: str = ""
    core: str = ""
    core_url: str = ""
    openocd_target: str = ""


@dataclass
class JtagConfig:
    """OpenOCD JTAG/SWD configuration."""
    interface: str   # OpenOCD interface config name: "stlink", "jlink", "cmsis-dap"
    target: str      # OpenOCD target config name: "stm32f4x", "nrf52", "esp32"


@dataclass
class DetectedBoard:
    """A board detected on a specific port."""
    board: Board
    port: str
    toolchain_name: str


class Toolchain(ABC):
    """Abstract base class for microcontroller toolchains."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable toolchain name (e.g., 'Arduino', 'PlatformIO')."""

    @abstractmethod
    def detect_project(self, path: Path) -> bool:
        """Return True if this directory contains a project for this toolchain."""

    @abstractmethod
    def detect_boards(self) -> list[DetectedBoard]:
        """Detect connected boards using this toolchain's detection method."""

    @abstractmethod
    def compile_command(self, board: Board) -> str:
        """Return the compile command string."""

    @abstractmethod
    def upload_command(self, board: Board, port: str) -> str:
        """Return the upload command string."""

    @abstractmethod
    def serial_config(self, board: Board) -> dict:
        """Return serial config: {"baud_rate": int, "boot_delay": int}."""

    @abstractmethod
    def board_info(self, board: Board) -> dict:
        """Return board-specific info for the template."""

    def setup_info(self, board: Board) -> str | None:
        """Return setup/installation instructions, or None if not needed."""
        return None

    def monitor_command(self, board: Board, port: str) -> str | None:
        """Return the serial monitor command, if the toolchain provides one."""
        return None

    def doctor(self) -> dict:
        """Check if this toolchain is installed. Returns {"ok": bool, "message": str}."""
        return {"ok": True, "message": "No checks configured"}

    def scaffold(self, board: Board, path: Path) -> None:
        """Create a new project in the given directory. Optional."""
        raise NotImplementedError(f"{self.name} does not support project scaffolding")

    def list_boards(self) -> list[Board]:
        """List all boards this toolchain supports. Optional."""
        return []

    def get_board(self, slug: str) -> Board | None:
        """Get a board by slug. Optional."""
        for b in self.list_boards():
            if b.slug == slug:
                return b
        return None
