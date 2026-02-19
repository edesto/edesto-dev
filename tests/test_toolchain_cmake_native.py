"""Tests for the CMake/Make native (bare-metal) toolchain."""

from pathlib import Path
from unittest.mock import patch

import pytest
from edesto_dev.toolchains.cmake_native import CMakeNativeToolchain
from edesto_dev.toolchain import Board


@pytest.fixture
def cmake_native():
    return CMakeNativeToolchain()


class TestCMakeNativeBasics:
    def test_name(self, cmake_native):
        assert cmake_native.name == "cmake-native"

    def test_detect_makefile_arm(self, cmake_native, tmp_path):
        (tmp_path / "Makefile").write_text("CC = arm-none-eabi-gcc\nall: main.o")
        assert cmake_native.detect_project(tmp_path) is True

    def test_detect_makefile_riscv(self, cmake_native, tmp_path):
        (tmp_path / "Makefile").write_text("CC = riscv32-unknown-elf-gcc")
        assert cmake_native.detect_project(tmp_path) is True

    def test_detect_makefile_cross_compile(self, cmake_native, tmp_path):
        (tmp_path / "Makefile").write_text("CROSS_COMPILE ?= arm-none-eabi-")
        assert cmake_native.detect_project(tmp_path) is True

    def test_detect_cmake_toolchain_file(self, cmake_native, tmp_path):
        (tmp_path / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.20)\n"
            "set(CMAKE_TOOLCHAIN_FILE toolchain.cmake)\n"
            "project(firmware)"
        )
        assert cmake_native.detect_project(tmp_path) is True

    def test_detect_cmake_arm(self, cmake_native, tmp_path):
        (tmp_path / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.20)\n"
            "set(CMAKE_C_COMPILER arm-none-eabi-gcc)\n"
            "project(firmware)"
        )
        assert cmake_native.detect_project(tmp_path) is True

    def test_detect_toolchain_cmake_file(self, cmake_native, tmp_path):
        (tmp_path / "toolchain.cmake").write_text("set(CMAKE_SYSTEM_NAME Generic)")
        assert cmake_native.detect_project(tmp_path) is True

    def test_detect_arm_cmake_file(self, cmake_native, tmp_path):
        (tmp_path / "arm-none-eabi.cmake").write_text("set(CMAKE_SYSTEM_NAME Generic)")
        assert cmake_native.detect_project(tmp_path) is True

    def test_no_project(self, cmake_native, tmp_path):
        assert cmake_native.detect_project(tmp_path) is False

    def test_plain_makefile_not_detected(self, cmake_native, tmp_path):
        (tmp_path / "Makefile").write_text("all:\n\tgcc main.c -o main")
        assert cmake_native.detect_project(tmp_path) is False

    def test_plain_cmake_not_detected(self, cmake_native, tmp_path):
        (tmp_path / "CMakeLists.txt").write_text("project(myapp)")
        assert cmake_native.detect_project(tmp_path) is False

    def test_excludes_zephyr(self, cmake_native, tmp_path):
        (tmp_path / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.20)\n"
            "find_package(Zephyr REQUIRED)\n"
            "set(CMAKE_TOOLCHAIN_FILE toolchain.cmake)\n"
            "project(firmware)"
        )
        assert cmake_native.detect_project(tmp_path) is False

    def test_excludes_espidf_sdkconfig(self, cmake_native, tmp_path):
        (tmp_path / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.20)\n"
            "set(CMAKE_TOOLCHAIN_FILE toolchain.cmake)\n"
        )
        (tmp_path / "sdkconfig").write_text("")
        assert cmake_native.detect_project(tmp_path) is False

    def test_excludes_espidf_main_dir(self, cmake_native, tmp_path):
        (tmp_path / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.20)\n"
            "set(CMAKE_TOOLCHAIN_FILE toolchain.cmake)\n"
        )
        main = tmp_path / "main"
        main.mkdir()
        (main / "CMakeLists.txt").write_text("idf_component_register()")
        assert cmake_native.detect_project(tmp_path) is False


class TestCMakeNativeCommands:
    def test_compile_command(self, cmake_native):
        board = Board(slug="stm32f4", name="STM32F4", baud_rate=115200)
        assert cmake_native.compile_command(board) == "cmake --build build"

    def test_upload_with_openocd(self, cmake_native):
        board = Board(slug="stm32f4", name="STM32F4", baud_rate=115200, openocd_target="stm32f4x")
        cmd = cmake_native.upload_command(board, "/dev/ttyACM0")
        assert "openocd" in cmd
        assert "stm32f4x" in cmd
        assert "program" in cmd

    def test_upload_without_openocd(self, cmake_native):
        board = Board(slug="custom", name="Custom", baud_rate=115200)
        cmd = cmake_native.upload_command(board, "/dev/ttyACM0")
        assert cmd == "make flash"

    def test_monitor_command(self, cmake_native):
        board = Board(slug="stm32f4", name="STM32F4", baud_rate=115200)
        cmd = cmake_native.monitor_command(board, "/dev/ttyACM0")
        assert "/dev/ttyACM0" in cmd
        assert "115200" in cmd


class TestCMakeNativeDoctor:
    @patch("shutil.which", side_effect=lambda cmd: {
        "arm-none-eabi-gcc": "/usr/bin/arm-none-eabi-gcc",
        "cmake": "/usr/bin/cmake",
        "make": "/usr/bin/make",
    }.get(cmd))
    def test_doctor_ok_cmake(self, mock_which, cmake_native):
        result = cmake_native.doctor()
        assert result["ok"] is True
        assert "cmake" in result["message"]

    @patch("shutil.which", side_effect=lambda cmd: {
        "arm-none-eabi-gcc": "/usr/bin/arm-none-eabi-gcc",
        "cmake": None,
        "make": "/usr/bin/make",
    }.get(cmd))
    def test_doctor_ok_make(self, mock_which, cmake_native):
        result = cmake_native.doctor()
        assert result["ok"] is True
        assert "make" in result["message"]

    @patch("shutil.which", return_value=None)
    def test_doctor_missing_all(self, mock_which, cmake_native):
        result = cmake_native.doctor()
        assert result["ok"] is False

    @patch("shutil.which", side_effect=lambda cmd: {
        "arm-none-eabi-gcc": None,
        "cmake": "/usr/bin/cmake",
        "make": "/usr/bin/make",
    }.get(cmd))
    def test_doctor_missing_gcc(self, mock_which, cmake_native):
        result = cmake_native.doctor()
        assert result["ok"] is False
        assert "arm-none-eabi-gcc" in result["message"]
