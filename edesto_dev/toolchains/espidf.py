"""ESP-IDF toolchain for edesto-dev."""

import shutil
from pathlib import Path

from edesto_dev.toolchain import Toolchain, Board, DetectedBoard
from edesto_dev.toolchains import register_toolchain


class EspIdfToolchain(Toolchain):

    @property
    def name(self):
        return "espidf"

    def detect_project(self, path: Path) -> bool:
        # ESP-IDF projects have CMakeLists.txt + either sdkconfig or main/ directory
        if not (path / "CMakeLists.txt").exists():
            return False
        if (path / "sdkconfig").exists():
            return True
        main_dir = path / "main"
        if main_dir.is_dir() and (main_dir / "CMakeLists.txt").exists():
            return True
        return False

    def detect_boards(self) -> list[DetectedBoard]:
        return []  # ESP-IDF board detection is port-based, skip for v1

    def compile_command(self, board: Board) -> str:
        return "idf.py build"

    def upload_command(self, board: Board, port: str) -> str:
        return f"idf.py -p {port} flash"

    def monitor_command(self, board: Board, port: str) -> str:
        return f"idf.py -p {port} monitor"

    def setup_info(self, board: Board) -> str | None:
        return "Activate ESP-IDF before compiling: `source $IDF_PATH/export.sh`"

    def serial_config(self, board: Board) -> dict:
        return {"baud_rate": board.baud_rate, "boot_delay": 5}

    def board_info(self, board: Board) -> dict:
        return {
            "pitfalls": board.pitfalls if board.pitfalls else None,
            "pin_notes": board.pin_notes if board.pin_notes else None,
        }

    def doctor(self) -> dict:
        if shutil.which("idf.py"):
            return {"ok": True, "message": "ESP-IDF (idf.py) found"}
        return {"ok": False, "message": "ESP-IDF not found. Install: https://docs.espressif.com/projects/esp-idf/en/latest/esp32/get-started/"}

    def scaffold(self, board: Board, path: Path) -> None:
        import subprocess
        subprocess.run(["idf.py", "create-project", str(path.name)], cwd=path.parent, check=True)


register_toolchain(EspIdfToolchain())
