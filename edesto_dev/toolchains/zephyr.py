"""Zephyr RTOS toolchain for edesto-dev."""

import shutil
from pathlib import Path

from edesto_dev.toolchain import Toolchain, Board, DetectedBoard
from edesto_dev.toolchains import register_toolchain


class ZephyrToolchain(Toolchain):

    @property
    def name(self):
        return "zephyr"

    def detect_project(self, path: Path) -> bool:
        """Detect a Zephyr project by prj.conf, west.yml, or CMakeLists.txt with Zephyr."""
        if (path / "prj.conf").exists():
            return True
        if (path / "west.yml").exists():
            return True
        cmake_file = path / "CMakeLists.txt"
        if cmake_file.exists():
            try:
                content = cmake_file.read_text()
                if "find_package(Zephyr" in content:
                    return True
            except OSError:
                pass
        return False

    def detect_boards(self) -> list[DetectedBoard]:
        return []

    def compile_command(self, board: Board) -> str:
        return f"west build -b {board.slug} ."

    def upload_command(self, board: Board, port: str) -> str:
        return "west flash"

    def monitor_command(self, board: Board, port: str) -> str:
        return f"python -m serial.tools.miniterm {port} {board.baud_rate}"

    def setup_info(self, board: Board) -> str | None:
        return "Install Zephyr: https://docs.zephyrproject.org/latest/develop/getting_started/index.html"

    def serial_config(self, board: Board) -> dict:
        return {"baud_rate": board.baud_rate, "boot_delay": 3}

    def board_info(self, board: Board) -> dict:
        return {
            "pitfalls": board.pitfalls if board.pitfalls else None,
            "pin_notes": board.pin_notes if board.pin_notes else None,
        }

    def doctor(self) -> dict:
        if shutil.which("west"):
            return {"ok": True, "message": "west (Zephyr meta-tool) found"}
        return {"ok": False, "message": "west not found. Install: pip install west"}


register_toolchain(ZephyrToolchain())
