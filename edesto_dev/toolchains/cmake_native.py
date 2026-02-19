"""CMake/Make bare-metal toolchain for edesto-dev."""

import shutil
from pathlib import Path

from edesto_dev.toolchain import Toolchain, Board, DetectedBoard
from edesto_dev.toolchains import register_toolchain


class CMakeNativeToolchain(Toolchain):

    @property
    def name(self):
        return "cmake-native"

    def detect_project(self, path: Path) -> bool:
        """Detect a bare-metal CMake or Makefile project.

        Looks for:
        - Makefile with cross-compiler references (arm-none-eabi, riscv, CROSS_COMPILE)
        - CMakeLists.txt with toolchain file or cross-compiler (excluding ESP-IDF/Zephyr)
        - Standalone toolchain cmake files
        """
        # Check for Makefile with cross-compiler hints
        makefile = path / "Makefile"
        if makefile.exists():
            try:
                content = makefile.read_text()
                if any(hint in content for hint in ("arm-none-eabi", "riscv32", "riscv64", "CROSS_COMPILE")):
                    return True
            except OSError:
                pass

        # Check for CMakeLists.txt with toolchain file (exclude ESP-IDF and Zephyr)
        cmake_file = path / "CMakeLists.txt"
        if cmake_file.exists():
            try:
                content = cmake_file.read_text()
                # Exclude ESP-IDF and Zephyr projects
                if "find_package(Zephyr" in content:
                    return False
                if (path / "sdkconfig").exists():
                    return False
                main_dir = path / "main"
                if main_dir.is_dir() and (main_dir / "CMakeLists.txt").exists():
                    return False
                if "CMAKE_TOOLCHAIN_FILE" in content or "arm-none-eabi" in content:
                    return True
            except OSError:
                pass

        # Check for standalone toolchain cmake files
        if (path / "toolchain.cmake").exists() or (path / "arm-none-eabi.cmake").exists():
            return True

        return False

    def detect_boards(self) -> list[DetectedBoard]:
        return []

    def compile_command(self, board: Board) -> str:
        return "cmake --build build"

    def upload_command(self, board: Board, port: str) -> str:
        if board.openocd_target:
            return (
                f"openocd -f interface/stlink.cfg -f target/{board.openocd_target}.cfg "
                f'-c "program build/firmware.elf verify reset exit"'
            )
        return "make flash"

    def monitor_command(self, board: Board, port: str) -> str:
        return f"python -m serial.tools.miniterm {port} {board.baud_rate}"

    def setup_info(self, board: Board) -> str | None:
        return "Install ARM toolchain: `apt install gcc-arm-none-eabi` (Linux) or `brew install arm-none-eabi-gcc` (macOS)"

    def serial_config(self, board: Board) -> dict:
        return {"baud_rate": board.baud_rate, "boot_delay": 3}

    def board_info(self, board: Board) -> dict:
        return {
            "pitfalls": board.pitfalls if board.pitfalls else None,
            "pin_notes": board.pin_notes if board.pin_notes else None,
        }

    def doctor(self) -> dict:
        gcc = shutil.which("arm-none-eabi-gcc")
        cmake = shutil.which("cmake")
        make = shutil.which("make")
        if gcc and (cmake or make):
            build_tool = "cmake" if cmake else "make"
            return {"ok": True, "message": f"arm-none-eabi-gcc and {build_tool} found"}
        missing = []
        if not gcc:
            missing.append("arm-none-eabi-gcc")
        if not cmake and not make:
            missing.append("cmake or make")
        return {"ok": False, "message": f"Missing: {', '.join(missing)}"}


register_toolchain(CMakeNativeToolchain())
