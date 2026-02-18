"""PlatformIO toolchain for edesto-dev."""

import shutil
from pathlib import Path

from edesto_dev.toolchain import Toolchain, Board, DetectedBoard
from edesto_dev.toolchains import register_toolchain


class PlatformIOToolchain(Toolchain):

    @property
    def name(self):
        return "platformio"

    def detect_project(self, path: Path) -> bool:
        return (path / "platformio.ini").exists()

    def detect_boards(self) -> list[DetectedBoard]:
        return []  # PlatformIO board detection via pio device list is complex, skip for v1

    def compile_command(self, board: Board) -> str:
        return "pio run"

    def upload_command(self, board: Board, port: str) -> str:
        return f"pio run --target upload --upload-port {port}"

    def monitor_command(self, board: Board, port: str) -> str:
        return f"pio device monitor --port {port} --baud {board.baud_rate}"

    def serial_config(self, board: Board) -> dict:
        return {"baud_rate": board.baud_rate, "boot_delay": 3}

    def board_info(self, board: Board) -> dict:
        return {
            "pitfalls": board.pitfalls if board.pitfalls else None,
            "pin_notes": board.pin_notes if board.pin_notes else None,
        }

    def doctor(self) -> dict:
        if shutil.which("pio"):
            return {"ok": True, "message": "PlatformIO CLI found"}
        return {"ok": False, "message": "PlatformIO CLI not found. Install: https://platformio.org/install/cli"}

    def scaffold(self, board: Board, path: Path) -> None:
        import subprocess
        subprocess.run(["pio", "project", "init", "--board", board.slug], cwd=path, check=True)


register_toolchain(PlatformIOToolchain())
