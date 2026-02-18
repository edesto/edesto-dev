"""MicroPython toolchain for edesto-dev."""

import shutil
from pathlib import Path

from edesto_dev.toolchain import Toolchain, Board, DetectedBoard
from edesto_dev.toolchains import register_toolchain


class MicroPythonToolchain(Toolchain):

    @property
    def name(self):
        return "micropython"

    def detect_project(self, path: Path) -> bool:
        # MicroPython projects have boot.py and/or main.py
        # Only match if there are NO .ino files (avoid false positives)
        if any(path.glob("*.ino")):
            return False
        return (path / "boot.py").exists() or (path / "main.py").exists()

    def detect_boards(self) -> list[DetectedBoard]:
        return []  # MicroPython board detection via mpremote, skip for v1

    def compile_command(self, board: Board) -> str:
        return "# No compile step — MicroPython runs .py files directly"

    def upload_command(self, board: Board, port: str) -> str:
        return f"mpremote connect {port} cp main.py :main.py"

    def monitor_command(self, board: Board, port: str) -> str:
        return f"mpremote connect {port} repl"

    def serial_config(self, board: Board) -> dict:
        return {"baud_rate": board.baud_rate, "boot_delay": 2}

    def board_info(self, board: Board) -> dict:
        return {
            "pitfalls": [
                "MicroPython has no compile step — files are copied directly to the board.",
                "Use `mpremote` to copy files and interact with the REPL.",
                "After copying files, reset the board to run the new code.",
                "Memory is limited — avoid large data structures.",
            ] + (board.pitfalls if board.pitfalls else []),
        }

    def doctor(self) -> dict:
        if shutil.which("mpremote"):
            return {"ok": True, "message": "mpremote found"}
        return {"ok": False, "message": "mpremote not found. Install: pip install mpremote"}

    def scaffold(self, board: Board, path: Path) -> None:
        (path / "boot.py").write_text("# boot.py — runs on startup\n")
        (path / "main.py").write_text("# main.py — your application code\nimport time\n\nwhile True:\n    print('[READY]')\n    time.sleep(1)\n")


register_toolchain(MicroPythonToolchain())
