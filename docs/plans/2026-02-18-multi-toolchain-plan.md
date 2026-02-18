# Multi-Toolchain Support Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `edesto init` work for any microcontroller by auto-detecting the toolchain from project files and the board from USB, then generating a CLAUDE.md with the right compile/upload/validate commands.

**Architecture:** Introduce a `Toolchain` ABC that encapsulates compile/upload/detect/scaffold/board-info per build system. Arduino becomes one implementation alongside PlatformIO, ESP-IDF, MicroPython, and a custom/TOML fallback. A detection layer resolves toolchain from project files and board from USB. The CLAUDE.md template becomes generic, pulling all commands from the toolchain.

**Tech Stack:** Python 3.10+, click, pyserial, tomllib (stdlib in 3.11+, tomli backport for 3.10)

**Design doc:** `docs/plans/2026-02-18-multi-toolchain-design.md`

---

### Task 1: Create the Toolchain ABC and Board dataclass

**Files:**
- Create: `edesto_dev/toolchain.py`
- Test: `tests/test_toolchain.py`

**Step 1: Write the failing test**

```python
# tests/test_toolchain.py
"""Tests for toolchain base class."""

import pytest
from edesto_dev.toolchain import Toolchain, Board


class TestBoard:
    def test_board_has_required_fields(self):
        board = Board(
            slug="test-board",
            name="Test Board",
            baud_rate=115200,
        )
        assert board.slug == "test-board"
        assert board.name == "Test Board"
        assert board.baud_rate == 115200
        assert board.capabilities == []
        assert board.pins == {}
        assert board.pitfalls == []
        assert board.pin_notes == []

    def test_board_with_all_fields(self):
        board = Board(
            slug="full-board",
            name="Full Board",
            baud_rate=9600,
            capabilities=["wifi"],
            pins={"led": 13},
            pitfalls=["Watch out"],
            pin_notes=["GPIO 13: LED"],
        )
        assert board.capabilities == ["wifi"]
        assert board.pins == {"led": 13}


class TestToolchainABC:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            Toolchain()

    def test_has_required_abstract_methods(self):
        # Verify all abstract methods exist
        abstract_methods = Toolchain.__abstractmethods__
        assert "name" in abstract_methods
        assert "detect_project" in abstract_methods
        assert "detect_boards" in abstract_methods
        assert "compile_command" in abstract_methods
        assert "upload_command" in abstract_methods
        assert "serial_config" in abstract_methods
        assert "board_info" in abstract_methods
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_toolchain.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'edesto_dev.toolchain'`

**Step 3: Write minimal implementation**

```python
# edesto_dev/toolchain.py
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
        """Return the compile command string for CLAUDE.md."""

    @abstractmethod
    def upload_command(self, board: Board, port: str) -> str:
        """Return the upload command string for CLAUDE.md."""

    @abstractmethod
    def serial_config(self, board: Board) -> dict:
        """Return serial config: {"baud_rate": int, "boot_delay": int}."""

    @abstractmethod
    def board_info(self, board: Board) -> dict:
        """Return board-specific info for CLAUDE.md template."""

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
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_toolchain.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add edesto_dev/toolchain.py tests/test_toolchain.py
git commit -m "feat: add Toolchain ABC and generic Board dataclass"
```

---

### Task 2: Create the toolchain registry

**Files:**
- Create: `edesto_dev/toolchains/__init__.py`
- Test: `tests/test_registry.py`

**Step 1: Write the failing test**

```python
# tests/test_registry.py
"""Tests for toolchain registry."""

from edesto_dev.toolchains import get_toolchain, list_toolchains, register_toolchain
from edesto_dev.toolchain import Toolchain, Board, DetectedBoard
from pathlib import Path


class _DummyToolchain(Toolchain):
    """Minimal concrete toolchain for testing."""

    @property
    def name(self):
        return "dummy"

    def detect_project(self, path):
        return False

    def detect_boards(self):
        return []

    def compile_command(self, board):
        return "dummy compile"

    def upload_command(self, board, port):
        return "dummy upload"

    def serial_config(self, board):
        return {"baud_rate": 115200, "boot_delay": 3}

    def board_info(self, board):
        return {}


class TestRegistry:
    def test_register_and_get(self):
        tc = _DummyToolchain()
        register_toolchain(tc)
        assert get_toolchain("dummy") is tc

    def test_list_toolchains(self):
        tc = _DummyToolchain()
        register_toolchain(tc)
        names = [t.name for t in list_toolchains()]
        assert "dummy" in names

    def test_get_unknown_returns_none(self):
        assert get_toolchain("nonexistent_xyz") is None
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_registry.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# edesto_dev/toolchains/__init__.py
"""Toolchain registry for edesto-dev."""

from edesto_dev.toolchain import Toolchain

_REGISTRY: dict[str, Toolchain] = {}


def register_toolchain(toolchain: Toolchain) -> None:
    """Register a toolchain by its name."""
    _REGISTRY[toolchain.name] = toolchain


def get_toolchain(name: str) -> Toolchain | None:
    """Get a toolchain by name."""
    return _REGISTRY.get(name)


def list_toolchains() -> list[Toolchain]:
    """Return all registered toolchains."""
    return list(_REGISTRY.values())
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_registry.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add edesto_dev/toolchains/__init__.py tests/test_registry.py
git commit -m "feat: add toolchain registry"
```

---

### Task 3: Create Arduino toolchain (migrate from boards.py)

This is the largest task. The 12 Arduino board definitions and arduino-cli detection logic move from `boards.py` into `toolchains/arduino.py`.

**Files:**
- Create: `edesto_dev/toolchains/arduino.py`
- Test: `tests/test_toolchain_arduino.py`

**Step 1: Write the failing test**

```python
# tests/test_toolchain_arduino.py
"""Tests for the Arduino toolchain."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from edesto_dev.toolchains.arduino import ArduinoToolchain


@pytest.fixture
def arduino():
    return ArduinoToolchain()


class TestArduinoToolchainBasics:
    def test_name(self, arduino):
        assert arduino.name == "arduino"

    def test_list_boards_returns_12(self, arduino):
        boards = arduino.list_boards()
        assert len(boards) == 12

    def test_get_board_esp32(self, arduino):
        board = arduino.get_board("esp32")
        assert board is not None
        assert board.name == "ESP32"
        assert board.baud_rate == 115200

    def test_get_board_arduino_uno(self, arduino):
        board = arduino.get_board("arduino-uno")
        assert board is not None
        assert board.baud_rate == 9600

    def test_get_board_unknown(self, arduino):
        assert arduino.get_board("nonexistent") is None


class TestArduinoCommands:
    def test_compile_command(self, arduino):
        board = arduino.get_board("esp32")
        cmd = arduino.compile_command(board)
        assert "arduino-cli compile" in cmd
        assert board.fqbn in cmd

    def test_upload_command(self, arduino):
        board = arduino.get_board("esp32")
        cmd = arduino.upload_command(board, "/dev/ttyUSB0")
        assert "arduino-cli upload" in cmd
        assert board.fqbn in cmd
        assert "/dev/ttyUSB0" in cmd

    def test_monitor_command(self, arduino):
        board = arduino.get_board("esp32")
        cmd = arduino.monitor_command(board, "/dev/ttyUSB0")
        assert "arduino-cli monitor" in cmd
        assert "/dev/ttyUSB0" in cmd


class TestArduinoDetectProject:
    def test_detects_ino_file(self, arduino, tmp_path):
        (tmp_path / "sketch.ino").write_text("void setup() {}")
        assert arduino.detect_project(tmp_path) is True

    def test_no_ino_file(self, arduino, tmp_path):
        (tmp_path / "main.py").write_text("print('hi')")
        assert arduino.detect_project(tmp_path) is False


class TestArduinoDetectBoards:
    ARDUINO_CLI_ONE_BOARD = json.dumps({
        "detected_ports": [{
            "matching_boards": [{"name": "ESP32 Dev Module", "fqbn": "esp32:esp32:esp32"}],
            "port": {"address": "/dev/cu.usbserial-0001", "protocol": "serial"},
        }]
    })

    @patch("edesto_dev.toolchains.arduino.subprocess.run")
    def test_detects_board(self, mock_run, arduino):
        mock = MagicMock()
        mock.stdout = self.ARDUINO_CLI_ONE_BOARD
        mock.returncode = 0
        mock_run.return_value = mock
        detected = arduino.detect_boards()
        assert len(detected) == 1
        assert detected[0].board.slug == "esp32"
        assert detected[0].port == "/dev/cu.usbserial-0001"
        assert detected[0].toolchain_name == "arduino"

    @patch("edesto_dev.toolchains.arduino.subprocess.run", side_effect=FileNotFoundError)
    def test_no_arduino_cli(self, mock_run, arduino):
        assert arduino.detect_boards() == []


class TestArduinoDoctor:
    @patch("shutil.which", return_value="/usr/local/bin/arduino-cli")
    def test_doctor_ok(self, mock_which, arduino):
        result = arduino.doctor()
        assert result["ok"] is True

    @patch("shutil.which", return_value=None)
    def test_doctor_missing(self, mock_which, arduino):
        result = arduino.doctor()
        assert result["ok"] is False


class TestArduinoSerialConfig:
    def test_esp32_config(self, arduino):
        board = arduino.get_board("esp32")
        config = arduino.serial_config(board)
        assert config["baud_rate"] == 115200
        assert config["boot_delay"] == 3

    def test_uno_config(self, arduino):
        board = arduino.get_board("arduino-uno")
        config = arduino.serial_config(board)
        assert config["baud_rate"] == 9600
```

Note: The `Board` dataclass in `toolchain.py` needs an `fqbn` field added as an optional field for Arduino boards. Add `fqbn: str = ""` and `core: str = ""` and `core_url: str = ""` to the Board dataclass since these are Arduino-specific but harmless as empty defaults.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_toolchain_arduino.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write implementation**

Add Arduino-specific optional fields to `edesto_dev/toolchain.py` Board dataclass:

```python
@dataclass
class Board:
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
```

Then create `edesto_dev/toolchains/arduino.py` — migrate all 12 board definitions from `boards.py` and the `detect_boards()` logic. The ArduinoToolchain class wraps them in the Toolchain interface:

- `name` → `"arduino"`
- `detect_project(path)` → check for `*.ino` files
- `detect_boards()` → existing `detect_boards()` logic from `boards.py`, but returning `DetectedBoard` from `toolchain.py` with `toolchain_name="arduino"`
- `compile_command(board)` → `f"arduino-cli compile --fqbn {board.fqbn} ."`
- `upload_command(board, port)` → `f"arduino-cli upload --fqbn {board.fqbn} --port {port} ."`
- `monitor_command(board, port)` → `f"arduino-cli monitor --port {port} --config baudrate={board.baud_rate}"`
- `serial_config(board)` → `{"baud_rate": board.baud_rate, "boot_delay": 3}`
- `board_info(board)` → `{"capabilities": ..., "pins": ..., "pitfalls": ..., "pin_notes": ..., "includes": ...}`
- `doctor()` → check `shutil.which("arduino-cli")`
- `scaffold(board, path)` → `arduino-cli sketch new`
- `list_boards()` → return all 12 boards
- `get_board(slug)` → lookup by slug

Move the VID/PID hints and FQBN matching logic as well.

Register the Arduino toolchain at module load time: at the bottom of `arduino.py`, call `register_toolchain(ArduinoToolchain())`.

Also update `edesto_dev/toolchains/__init__.py` to import the arduino module so it auto-registers:

```python
# At the bottom of edesto_dev/toolchains/__init__.py
from edesto_dev.toolchains import arduino as _arduino  # noqa: F401 — auto-registers
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_toolchain_arduino.py -v`
Expected: PASS

**Step 5: Also verify existing tests still pass**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS (old boards.py is still there, untouched)

**Step 6: Commit**

```bash
git add edesto_dev/toolchain.py edesto_dev/toolchains/arduino.py edesto_dev/toolchains/__init__.py tests/test_toolchain_arduino.py
git commit -m "feat: add Arduino toolchain implementation with all 12 boards"
```

---

### Task 4: Create the detection system

**Files:**
- Create: `edesto_dev/detect.py`
- Test: `tests/test_detect.py`

**Step 1: Write the failing test**

```python
# tests/test_detect.py
"""Tests for toolchain and board detection."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from edesto_dev.detect import detect_toolchain, detect_all_boards


class TestDetectToolchain:
    def test_detects_arduino_from_ino_file(self, tmp_path):
        (tmp_path / "sketch.ino").write_text("void setup() {}")
        tc = detect_toolchain(tmp_path)
        assert tc is not None
        assert tc.name == "arduino"

    def test_detects_platformio_from_ini(self, tmp_path):
        (tmp_path / "platformio.ini").write_text("[env:esp32dev]")
        tc = detect_toolchain(tmp_path)
        assert tc is not None
        assert tc.name == "platformio"

    def test_platformio_takes_priority_over_arduino(self, tmp_path):
        """PlatformIO projects may contain .ino files."""
        (tmp_path / "platformio.ini").write_text("[env:esp32dev]")
        (tmp_path / "src" / "main.ino").mkdir(parents=True, exist_ok=True)
        tc = detect_toolchain(tmp_path)
        assert tc.name == "platformio"

    def test_returns_none_for_empty_dir(self, tmp_path):
        tc = detect_toolchain(tmp_path)
        assert tc is None

    def test_edesto_toml_takes_priority(self, tmp_path):
        (tmp_path / "sketch.ino").write_text("void setup() {}")
        (tmp_path / "edesto.toml").write_text('[toolchain]\nname = "custom"\ncompile = "make"\nupload = "make flash"')
        tc = detect_toolchain(tmp_path)
        assert tc is not None
        assert tc.name == "custom"
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_detect.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write implementation**

```python
# edesto_dev/detect.py
"""Project and board detection for edesto-dev."""

from pathlib import Path

from edesto_dev.toolchain import Toolchain, DetectedBoard
from edesto_dev.toolchains import list_toolchains, get_toolchain


# Priority order for toolchain detection from project files.
# Higher priority toolchains are checked first.
_DETECTION_PRIORITY = ["platformio", "espidf", "arduino", "micropython"]


def detect_toolchain(path: Path) -> Toolchain | None:
    """Detect the toolchain from project files in the given directory.

    Checks for edesto.toml first (user override), then scans project
    files in priority order.
    """
    # 1. Check for edesto.toml override
    toml_path = path / "edesto.toml"
    if toml_path.exists():
        custom = _load_custom_toolchain(toml_path)
        if custom:
            return custom

    # 2. Scan project files in priority order
    toolchains = {tc.name: tc for tc in list_toolchains()}
    for name in _DETECTION_PRIORITY:
        tc = toolchains.get(name)
        if tc and tc.detect_project(path):
            return tc

    # 3. Check any remaining registered toolchains not in priority list
    for tc in list_toolchains():
        if tc.name not in _DETECTION_PRIORITY and tc.detect_project(path):
            return tc

    return None


def detect_all_boards() -> list[DetectedBoard]:
    """Detect boards across all installed toolchains."""
    all_detected = []
    for tc in list_toolchains():
        try:
            detected = tc.detect_boards()
            all_detected.extend(detected)
        except Exception:
            continue
    return all_detected


def _load_custom_toolchain(toml_path: Path) -> Toolchain | None:
    """Load a custom toolchain from edesto.toml."""
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            return None

    try:
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)
    except Exception:
        return None

    tc_data = data.get("toolchain", {})
    if not tc_data.get("compile") or not tc_data.get("upload"):
        return None

    from edesto_dev.toolchains.custom import CustomToolchain
    serial_data = data.get("serial", {})
    return CustomToolchain(
        compile_cmd=tc_data["compile"],
        upload_cmd=tc_data["upload"],
        baud_rate=serial_data.get("baud_rate", 115200),
    )
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_detect.py -v`
Expected: Some tests PASS (arduino detection), some may need the custom/platformio toolchains created first. The edesto.toml and platformio tests will be completed in Tasks 7 and 10. For now, mark those as `@pytest.mark.skip("requires platformio/custom toolchain")` and come back.

**Step 5: Commit**

```bash
git add edesto_dev/detect.py tests/test_detect.py
git commit -m "feat: add toolchain detection from project files"
```

---

### Task 5: Refactor templates to be generic

**Files:**
- Modify: `edesto_dev/templates.py`
- Test: `tests/test_templates.py` (update existing tests)

**Step 1: Write the failing test**

Add a new test class to `tests/test_templates.py`:

```python
# Add to tests/test_templates.py
from edesto_dev.toolchain import Board


class TestGenericRender:
    def test_renders_with_toolchain_data(self):
        """Test that render_template works with generic toolchain data."""
        from edesto_dev.templates import render_generic_template
        result = render_generic_template(
            board_name="Test Board",
            toolchain_name="test-tool",
            port="/dev/ttyUSB0",
            baud_rate=115200,
            compile_command="make build",
            upload_command="make flash PORT=/dev/ttyUSB0",
            monitor_command="make monitor",
            boot_delay=3,
            board_info={},
        )
        assert "Test Board" in result
        assert "make build" in result
        assert "make flash" in result
        assert "/dev/ttyUSB0" in result
        assert "115200" in result
        assert "Development Loop" in result
        assert "[READY]" in result

    def test_no_unfilled_placeholders(self):
        from edesto_dev.templates import render_generic_template
        result = render_generic_template(
            board_name="Board",
            toolchain_name="tool",
            port="/dev/ttyUSB0",
            baud_rate=115200,
            compile_command="compile",
            upload_command="upload",
            monitor_command=None,
            boot_delay=3,
            board_info={},
        )
        import re
        placeholders = re.findall(r"\{[a-z_]+\}", result)
        assert placeholders == []
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_templates.py::TestGenericRender -v`
Expected: FAIL with `ImportError`

**Step 3: Write implementation**

Add `render_generic_template()` to `edesto_dev/templates.py`. Keep the existing `render_template()` function working (it now calls `render_generic_template` internally):

```python
def render_generic_template(
    board_name: str,
    toolchain_name: str,
    port: str,
    baud_rate: int,
    compile_command: str,
    upload_command: str,
    monitor_command: str | None,
    boot_delay: int,
    board_info: dict,
) -> str:
    """Render a CLAUDE.md for any toolchain."""
    sections = [
        _generic_header(board_name, toolchain_name, port, baud_rate),
        _generic_commands(compile_command, upload_command, monitor_command),
        _generic_dev_loop(compile_command, upload_command, boot_delay),
        _generic_validation(port, baud_rate),
        _datasheets(),
        _generic_board_info(board_name, board_info),
    ]
    return "\n".join(sections)
```

Implement each `_generic_*` helper — same structure as existing helpers but with generic parameters instead of Arduino-specific ones.

Update existing `render_template(board, port)` to delegate:

```python
def render_template(board: Board, port: str) -> str:
    """Legacy: render CLAUDE.md for an Arduino board. Delegates to render_generic_template."""
    return render_generic_template(
        board_name=board.name,
        toolchain_name="Arduino",
        port=port,
        baud_rate=board.baud_rate,
        compile_command=f"arduino-cli compile --fqbn {board.fqbn} .",
        upload_command=f"arduino-cli upload --fqbn {board.fqbn} --port {port} .",
        monitor_command=f"arduino-cli monitor --port {port} --config baudrate={board.baud_rate}",
        boot_delay=3,
        board_info={
            "capabilities": board.includes if board.includes else None,
            "pin_notes": board.pin_notes if board.pin_notes else None,
            "pitfalls": board.pitfalls if board.pitfalls else None,
        },
    )
```

**Step 4: Run ALL template tests**

Run: `python -m pytest tests/test_templates.py -v`
Expected: ALL PASS (both old and new tests)

**Step 5: Commit**

```bash
git add edesto_dev/templates.py tests/test_templates.py
git commit -m "feat: add generic template renderer, delegate Arduino template to it"
```

---

### Task 6: Add a helper to render from a Toolchain object

**Files:**
- Modify: `edesto_dev/templates.py`
- Test: `tests/test_templates.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_templates.py
class TestRenderFromToolchain:
    def test_renders_from_toolchain(self):
        from edesto_dev.templates import render_from_toolchain
        from edesto_dev.toolchains.arduino import ArduinoToolchain
        tc = ArduinoToolchain()
        board = tc.get_board("esp32")
        result = render_from_toolchain(tc, board, "/dev/ttyUSB0")
        assert "ESP32" in result
        assert "arduino-cli compile" in result
        assert "/dev/ttyUSB0" in result
        assert "Development Loop" in result
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_templates.py::TestRenderFromToolchain -v`
Expected: FAIL

**Step 3: Write implementation**

```python
# Add to edesto_dev/templates.py
def render_from_toolchain(toolchain: "Toolchain", board: "Board", port: str) -> str:
    """Render CLAUDE.md using a Toolchain and Board."""
    config = toolchain.serial_config(board)
    info = toolchain.board_info(board)
    return render_generic_template(
        board_name=board.name,
        toolchain_name=toolchain.name,
        port=port,
        baud_rate=config["baud_rate"],
        compile_command=toolchain.compile_command(board),
        upload_command=toolchain.upload_command(board, port),
        monitor_command=toolchain.monitor_command(board, port),
        boot_delay=config.get("boot_delay", 3),
        board_info=info,
    )
```

**Step 4: Run tests**

Run: `python -m pytest tests/test_templates.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add edesto_dev/templates.py tests/test_templates.py
git commit -m "feat: add render_from_toolchain helper"
```

---

### Task 7: Refactor CLI to use toolchain system

**Files:**
- Modify: `edesto_dev/cli.py`
- Modify: `tests/test_cli.py`

This is a careful refactoring. The CLI needs to:
1. Use `detect_toolchain()` to find the toolchain from project files
2. Use `detect_all_boards()` or `toolchain.detect_boards()` for board detection
3. Use `render_from_toolchain()` for template rendering
4. Add `--toolchain` flag
5. Keep backward compatibility with `--board` and `--port`

**Step 1: Update test expectations**

Update `tests/test_cli.py`:

- Change imports from `edesto_dev.boards` to `edesto_dev.toolchain`
- Update mock paths from `edesto_dev.cli.detect_boards` to `edesto_dev.cli.detect_all_boards` (or however detection is called)
- Keep all existing test assertions — the output should be the same
- Add new tests for `--toolchain` flag

Key new tests:

```python
class TestInitWithToolchain:
    def test_toolchain_flag(self, runner):
        with runner.isolated_filesystem():
            Path("sketch.ino").write_text("void setup() {}")
            result = runner.invoke(main, ["init", "--board", "esp32", "--port", "/dev/ttyUSB0", "--toolchain", "arduino"])
            assert result.exit_code == 0
            assert Path("CLAUDE.md").exists()
```

**Step 2: Refactor cli.py**

Replace imports and update the `init` command:

```python
from edesto_dev.detect import detect_toolchain, detect_all_boards
from edesto_dev.toolchains import get_toolchain, list_toolchains
from edesto_dev.templates import render_from_toolchain
```

Update `init()`:
1. If `--toolchain` provided, use that
2. Else, call `detect_toolchain(Path.cwd())`
3. If no toolchain detected and no `--board`, call `detect_all_boards()` and ask
4. If still nothing, ask user for compile/upload commands (custom toolchain)
5. Render with `render_from_toolchain()`

Update `boards()`:
- List boards grouped by toolchain
- Add `--toolchain` filter

Update `doctor()`:
- Check all registered toolchains

**Step 3: Run ALL tests**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add edesto_dev/cli.py tests/test_cli.py
git commit -m "refactor: CLI uses toolchain system for detection and rendering"
```

---

### Task 8: Add PlatformIO toolchain

**Files:**
- Create: `edesto_dev/toolchains/platformio.py`
- Test: `tests/test_toolchain_platformio.py`

**Step 1: Write the failing test**

```python
# tests/test_toolchain_platformio.py
"""Tests for the PlatformIO toolchain."""

from pathlib import Path
from unittest.mock import patch

import pytest
from edesto_dev.toolchains.platformio import PlatformIOToolchain


@pytest.fixture
def pio():
    return PlatformIOToolchain()


class TestPlatformIOBasics:
    def test_name(self, pio):
        assert pio.name == "platformio"

    def test_detect_project(self, pio, tmp_path):
        (tmp_path / "platformio.ini").write_text("[env:esp32dev]")
        assert pio.detect_project(tmp_path) is True

    def test_no_project(self, pio, tmp_path):
        assert pio.detect_project(tmp_path) is False

    def test_compile_command(self, pio):
        from edesto_dev.toolchain import Board
        board = Board(slug="esp32dev", name="ESP32", baud_rate=115200)
        assert pio.compile_command(board) == "pio run"

    def test_upload_command(self, pio):
        from edesto_dev.toolchain import Board
        board = Board(slug="esp32dev", name="ESP32", baud_rate=115200)
        cmd = pio.upload_command(board, "/dev/ttyUSB0")
        assert "pio run" in cmd
        assert "--target upload" in cmd
        assert "/dev/ttyUSB0" in cmd

    def test_monitor_command(self, pio):
        from edesto_dev.toolchain import Board
        board = Board(slug="esp32dev", name="ESP32", baud_rate=115200)
        cmd = pio.monitor_command(board, "/dev/ttyUSB0")
        assert "pio device monitor" in cmd

    @patch("shutil.which", return_value="/usr/local/bin/pio")
    def test_doctor_ok(self, mock_which, pio):
        result = pio.doctor()
        assert result["ok"] is True

    @patch("shutil.which", return_value=None)
    def test_doctor_missing(self, mock_which, pio):
        result = pio.doctor()
        assert result["ok"] is False
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_toolchain_platformio.py -v`
Expected: FAIL

**Step 3: Write implementation**

```python
# edesto_dev/toolchains/platformio.py
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
        # PlatformIO device detection via `pio device list --json-output`
        # For now, return empty — PlatformIO board detection is complex
        # and most users will have project files that identify the board
        return []

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
```

Auto-register by importing in `toolchains/__init__.py`:

```python
from edesto_dev.toolchains import platformio as _platformio  # noqa: F401
```

**Step 4: Run tests**

Run: `python -m pytest tests/test_toolchain_platformio.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add edesto_dev/toolchains/platformio.py tests/test_toolchain_platformio.py edesto_dev/toolchains/__init__.py
git commit -m "feat: add PlatformIO toolchain"
```

---

### Task 9: Add ESP-IDF toolchain

**Files:**
- Create: `edesto_dev/toolchains/espidf.py`
- Test: `tests/test_toolchain_espidf.py`

Same TDD pattern as Task 8. Key details:

- `name` → `"espidf"`
- `detect_project(path)` → check for `CMakeLists.txt` + (`sdkconfig` or `main/` dir with `CMakeLists.txt` containing `idf_component_register`)
- `compile_command()` → `"idf.py build"`
- `upload_command(board, port)` → `f"idf.py -p {port} flash"`
- `monitor_command(board, port)` → `f"idf.py -p {port} monitor"`
- `doctor()` → check `shutil.which("idf.py")`
- `scaffold()` → `idf.py create-project`

Register in `toolchains/__init__.py`.

**Commit:**

```bash
git add edesto_dev/toolchains/espidf.py tests/test_toolchain_espidf.py edesto_dev/toolchains/__init__.py
git commit -m "feat: add ESP-IDF toolchain"
```

---

### Task 10: Add MicroPython toolchain

**Files:**
- Create: `edesto_dev/toolchains/micropython.py`
- Test: `tests/test_toolchain_micropython.py`

Same TDD pattern. Key details:

- `name` → `"micropython"`
- `detect_project(path)` → check for `boot.py` or `main.py` with MicroPython-style imports
- `compile_command()` → No compile step. Return a message explaining this: `"# No compile step — MicroPython runs .py files directly"`
- `upload_command(board, port)` → `f"mpremote connect {port} cp main.py :main.py"` (using mpremote)
- `monitor_command(board, port)` → `f"mpremote connect {port} repl"`
- `doctor()` → check `shutil.which("mpremote")`
- Special: the CLAUDE.md dev loop is different (no compile, just copy and reboot)

Register in `toolchains/__init__.py`.

**Commit:**

```bash
git add edesto_dev/toolchains/micropython.py tests/test_toolchain_micropython.py edesto_dev/toolchains/__init__.py
git commit -m "feat: add MicroPython toolchain"
```

---

### Task 11: Add Custom toolchain (edesto.toml fallback)

**Files:**
- Create: `edesto_dev/toolchains/custom.py`
- Test: `tests/test_toolchain_custom.py`

**Step 1: Write the failing test**

```python
# tests/test_toolchain_custom.py
"""Tests for the custom/TOML toolchain."""

import pytest
from edesto_dev.toolchains.custom import CustomToolchain
from edesto_dev.toolchain import Board


@pytest.fixture
def custom():
    return CustomToolchain(
        compile_cmd="make build",
        upload_cmd="make flash PORT={port}",
        baud_rate=115200,
    )


class TestCustomToolchain:
    def test_name(self, custom):
        assert custom.name == "custom"

    def test_compile_command(self, custom):
        board = Board(slug="myboard", name="My Board", baud_rate=115200)
        assert custom.compile_command(board) == "make build"

    def test_upload_command_interpolates_port(self, custom):
        board = Board(slug="myboard", name="My Board", baud_rate=115200)
        cmd = custom.upload_command(board, "/dev/ttyUSB0")
        assert cmd == "make flash PORT=/dev/ttyUSB0"

    def test_detect_project_always_false(self, custom):
        """Custom toolchain is loaded from edesto.toml, not detected."""
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            assert custom.detect_project(Path(d)) is False
```

**Step 2–4: Implement and test**

```python
# edesto_dev/toolchains/custom.py
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
        return False  # Custom is loaded from edesto.toml, not detected

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
```

Note: Do NOT register this in `__init__.py` — custom toolchains are created on demand from `edesto.toml`, not registered globally.

**Step 5: Commit**

```bash
git add edesto_dev/toolchains/custom.py tests/test_toolchain_custom.py
git commit -m "feat: add custom toolchain for edesto.toml fallback"
```

---

### Task 12: Wire up the custom toolchain fallback in CLI

**Files:**
- Modify: `edesto_dev/cli.py`
- Test: `tests/test_cli.py`

Add the interactive fallback to `init()`: when no toolchain is detected and no `--board` provided, ask the user for compile/upload commands and save to `edesto.toml`.

```python
# In the init command, after all detection fails:
compile_cmd = click.prompt("What command compiles your firmware?")
upload_cmd = click.prompt("What command uploads to the board?")
baud = click.prompt("What baud rate does your board use?", type=int, default=115200)
port = click.prompt("What serial port is your board on?") if not port else port

# Save to edesto.toml
toml_content = f'[toolchain]\nname = "custom"\ncompile = "{compile_cmd}"\nupload = "{upload_cmd}"\n\n[serial]\nbaud_rate = {baud}\nport = "{port}"\n'
Path("edesto.toml").write_text(toml_content)
```

Test with CliRunner input simulation.

**Commit:**

```bash
git add edesto_dev/cli.py tests/test_cli.py
git commit -m "feat: interactive custom toolchain fallback with edesto.toml"
```

---

### Task 13: Remove old boards.py and update all imports

**Files:**
- Delete: `edesto_dev/boards.py`
- Modify: `tests/test_boards.py` → rewrite to test via Arduino toolchain
- Modify: `tests/test_cli.py` → update any remaining old imports
- Modify: `tests/test_templates.py` → update imports

**Step 1: Update test imports**

Replace all `from edesto_dev.boards import ...` with equivalents from the new system:
- `get_board("esp32")` → `ArduinoToolchain().get_board("esp32")`
- `list_boards()` → `ArduinoToolchain().list_boards()`
- `detect_boards()` → `ArduinoToolchain().detect_boards()`
- `Board` → `from edesto_dev.toolchain import Board`
- `DetectedBoard` → `from edesto_dev.toolchain import DetectedBoard`
- `BoardNotFoundError` → can be removed or kept as a compatibility import

**Step 2: Verify backward compatibility**

If the old `boards.py` import paths are used externally (by users who pip-installed), consider adding a compatibility shim that re-exports from the new location. Otherwise, just delete.

**Step 3: Run ALL tests**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git rm edesto_dev/boards.py
git add tests/test_boards.py tests/test_cli.py tests/test_templates.py
git commit -m "refactor: remove boards.py, all boards now in Arduino toolchain"
```

---

### Task 14: Update pyproject.toml and package metadata

**Files:**
- Modify: `pyproject.toml`

Update:
- `keywords`: add "platformio", "esp-idf", "micropython", "embedded"
- `[tool.setuptools.packages.find]`: ensure `toolchains` subpackage is included
- Version bump to 0.4.0

**Commit:**

```bash
git add pyproject.toml
git commit -m "chore: update package metadata for multi-toolchain support"
```

---

### Task 15: Final integration test

**Files:**
- Add integration tests to `tests/test_cli.py`

Write end-to-end tests:

1. Arduino project: create `.ino` file → `edesto init` → verify CLAUDE.md has `arduino-cli` commands
2. PlatformIO project: create `platformio.ini` → `edesto init` → verify CLAUDE.md has `pio` commands
3. Custom project: empty dir → `edesto init` with input → verify `edesto.toml` created and CLAUDE.md has custom commands
4. Override: create `.ino` file + `edesto.toml` → verify TOML takes priority

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

**Commit:**

```bash
git add tests/test_cli.py
git commit -m "test: add end-to-end integration tests for multi-toolchain"
```
