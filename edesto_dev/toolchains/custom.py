"""Custom toolchain loaded from edesto.toml."""

from pathlib import Path
from edesto_dev.toolchain import Toolchain, Board, DetectedBoard


class CustomToolchain(Toolchain):
    def __init__(self, compile_cmd: str, upload_cmd: str, baud_rate: int = 115200):
        self._compile_cmd = compile_cmd
        self._upload_cmd = upload_cmd
        self._baud_rate = baud_rate

    @property
    def name(self):
        return "custom"

    def detect_project(self, path: Path) -> bool:
        return False  # Custom is loaded from edesto.toml, not detected from files

    def detect_boards(self) -> list[DetectedBoard]:
        return []

    def compile_command(self, board: Board) -> str:
        return self._compile_cmd

    def upload_command(self, board: Board, port: str) -> str:
        return self._upload_cmd.replace("{port}", port)

    def serial_config(self, board: Board) -> dict:
        return {"baud_rate": self._baud_rate, "boot_delay": 3}

    def board_info(self, board: Board) -> dict:
        return {}
