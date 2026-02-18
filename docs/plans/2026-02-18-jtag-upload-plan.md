# JTAG Upload Method Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Allow `edesto init` to set up boards that flash via JTAG/SWD (OpenOCD) instead of USB serial, both as an explicit `--upload jtag` option and as an auto-fallback when no USB serial boards are found.

**Architecture:** JTAG is an upload method, not a toolchain. A new `JtagConfig` dataclass holds probe/target info. The CLI gets a `--upload` flag and a JTAG setup flow. The template renderer accepts an optional `JtagConfig` and adjusts the header, upload command, and serial section accordingly. The existing USB serial path is untouched.

**Tech Stack:** Python, click (CLI), dataclasses, pytest, click.testing.CliRunner

---

### Task 1: Add `JtagConfig` dataclass and `openocd_target` to Board

**Files:**
- Modify: `edesto_dev/toolchain.py:1-31`
- Test: `tests/test_toolchain.py`

**Step 1: Write the failing test**

In `tests/test_toolchain.py`, add:

```python
from edesto_dev.toolchain import JtagConfig

class TestJtagConfig:
    def test_jtag_config_fields(self):
        cfg = JtagConfig(interface="stlink", target="stm32f4x")
        assert cfg.interface == "stlink"
        assert cfg.target == "stm32f4x"

    def test_board_openocd_target_defaults_empty(self):
        from edesto_dev.toolchain import Board
        b = Board(slug="test", name="Test", baud_rate=115200)
        assert b.openocd_target == ""

    def test_board_openocd_target_set(self):
        from edesto_dev.toolchain import Board
        b = Board(slug="test", name="Test", baud_rate=115200, openocd_target="stm32f4x")
        assert b.openocd_target == "stm32f4x"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_toolchain.py::TestJtagConfig -v`
Expected: FAIL — `ImportError: cannot import name 'JtagConfig'` and `TypeError: unexpected keyword argument 'openocd_target'`

**Step 3: Write minimal implementation**

In `edesto_dev/toolchain.py`, add `JtagConfig` dataclass after the `Board` class and add `openocd_target` field to `Board`:

```python
@dataclass
class JtagConfig:
    """OpenOCD JTAG/SWD configuration."""
    interface: str   # OpenOCD interface config name: "stlink", "jlink", "cmsis-dap"
    target: str      # OpenOCD target config name: "stm32f4x", "nrf52", "esp32"
```

Add to `Board` dataclass (after `core_url`):

```python
    openocd_target: str = ""
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_toolchain.py::TestJtagConfig -v`
Expected: PASS

**Step 5: Run full test suite to check nothing broke**

Run: `pytest tests/ -v`
Expected: All existing tests PASS

**Step 6: Commit**

```bash
git add edesto_dev/toolchain.py tests/test_toolchain.py
git commit -m "feat: add JtagConfig dataclass and openocd_target field to Board"
```

---

### Task 2: Add `openocd_target` to board definitions in Arduino toolchain

**Files:**
- Modify: `edesto_dev/toolchains/arduino.py` (board definitions, lines 36-538)
- Test: `tests/test_toolchain_arduino.py`

**Step 1: Write the failing test**

In `tests/test_toolchain_arduino.py`, add:

```python
class TestBoardOpenocdTargets:
    def test_stm32_nucleo_has_openocd_target(self):
        board = _arduino.get_board("stm32-nucleo")
        assert board.openocd_target == "stm32f4x"

    def test_esp32_has_openocd_target(self):
        board = _arduino.get_board("esp32")
        assert board.openocd_target == "esp32"

    def test_rp2040_has_openocd_target(self):
        board = _arduino.get_board("rp2040")
        assert board.openocd_target == "rp2040"

    def test_arduino_uno_has_no_openocd_target(self):
        board = _arduino.get_board("arduino-uno")
        assert board.openocd_target == ""
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_toolchain_arduino.py::TestBoardOpenocdTargets -v`
Expected: FAIL — `assert '' == 'stm32f4x'`

**Step 3: Write minimal implementation**

Add `openocd_target` to each board definition in `edesto_dev/toolchains/arduino.py`:

| Board slug    | `openocd_target` value |
|---------------|----------------------|
| esp32         | `"esp32"`            |
| esp32s3       | `"esp32s3"`          |
| esp32c3       | `"esp32c3"`          |
| esp32c6       | `"esp32c6"`          |
| esp8266       | `""` (no JTAG)       |
| arduino-uno   | `""` (no JTAG)       |
| arduino-nano  | `""` (no JTAG)       |
| arduino-mega  | `""` (no JTAG)       |
| rp2040        | `"rp2040"`           |
| teensy40      | `""` (uses teensy_loader) |
| teensy41      | `""` (uses teensy_loader) |
| stm32-nucleo  | `"stm32f4x"`         |

Add the field to each `Board(...)` constructor call that needs it. Boards that don't support JTAG keep the default `""`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_toolchain_arduino.py::TestBoardOpenocdTargets -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `pytest tests/ -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add edesto_dev/toolchains/arduino.py tests/test_toolchain_arduino.py
git commit -m "feat: add openocd_target to board definitions"
```

---

### Task 3: Add JTAG-aware template rendering

**Files:**
- Modify: `edesto_dev/templates.py:1-77` (add `jtag_config` parameter to `render_generic_template` and `render_from_toolchain`)
- Modify: `edesto_dev/templates.py:85-94` (`_generic_header` — JTAG variant)
- Modify: `edesto_dev/templates.py:153-191` (`_debugging` — conditional serial section)
- Modify: `edesto_dev/templates.py:485-504` (`_troubleshooting` — conditional for JTAG)
- Test: `tests/test_templates.py`

**Step 1: Write the failing tests**

In `tests/test_templates.py`, add:

```python
class TestJtagTemplateRendering:
    def test_jtag_header_says_connected_via_jtag(self):
        from edesto_dev.templates import render_generic_template
        from edesto_dev.toolchain import JtagConfig
        result = render_generic_template(
            board_name="STM32 Nucleo-64",
            toolchain_name="Arduino",
            port=None,
            baud_rate=115200,
            compile_command="arduino-cli compile --fqbn STMicroelectronics:stm32:Nucleo_64 .",
            upload_command='openocd -f interface/stlink.cfg -f target/stm32f4x.cfg -c "program build/firmware.elf verify reset exit"',
            monitor_command=None,
            boot_delay=3,
            board_info={},
            debug_tools=["openocd"],
            jtag_config=JtagConfig(interface="stlink", target="stm32f4x"),
        )
        assert "JTAG" in result or "jtag" in result.lower()
        assert "connected via USB" not in result

    def test_jtag_header_shows_probe_name(self):
        from edesto_dev.templates import render_generic_template
        from edesto_dev.toolchain import JtagConfig
        result = render_generic_template(
            board_name="STM32 Nucleo-64",
            toolchain_name="Arduino",
            port=None,
            baud_rate=115200,
            compile_command="compile",
            upload_command="upload",
            monitor_command=None,
            boot_delay=3,
            board_info={},
            debug_tools=["openocd"],
            jtag_config=JtagConfig(interface="stlink", target="stm32f4x"),
        )
        assert "stlink" in result.lower() or "ST-Link" in result

    def test_jtag_no_serial_section_when_no_port(self):
        from edesto_dev.templates import render_generic_template
        from edesto_dev.toolchain import JtagConfig
        result = render_generic_template(
            board_name="STM32 Nucleo-64",
            toolchain_name="Arduino",
            port=None,
            baud_rate=115200,
            compile_command="compile",
            upload_command="upload",
            monitor_command=None,
            boot_delay=3,
            board_info={},
            debug_tools=["openocd"],
            jtag_config=JtagConfig(interface="stlink", target="stm32f4x"),
        )
        assert "### Serial Output" not in result

    def test_jtag_with_serial_port_has_serial_section(self):
        from edesto_dev.templates import render_generic_template
        from edesto_dev.toolchain import JtagConfig
        result = render_generic_template(
            board_name="STM32 Nucleo-64",
            toolchain_name="Arduino",
            port="/dev/cu.usbmodem1103",
            baud_rate=115200,
            compile_command="compile",
            upload_command="upload",
            monitor_command=None,
            boot_delay=3,
            board_info={},
            debug_tools=["openocd"],
            jtag_config=JtagConfig(interface="stlink", target="stm32f4x"),
        )
        assert "### Serial Output" in result

    def test_jtag_always_has_openocd_in_debug_tools(self):
        from edesto_dev.templates import render_generic_template
        from edesto_dev.toolchain import JtagConfig
        result = render_generic_template(
            board_name="STM32 Nucleo-64",
            toolchain_name="Arduino",
            port=None,
            baud_rate=115200,
            compile_command="compile",
            upload_command="upload",
            monitor_command=None,
            boot_delay=3,
            board_info={},
            debug_tools=[],
            jtag_config=JtagConfig(interface="stlink", target="stm32f4x"),
        )
        assert "### JTAG/SWD" in result

    def test_jtag_no_serial_troubleshooting_when_no_port(self):
        from edesto_dev.templates import render_generic_template
        from edesto_dev.toolchain import JtagConfig
        result = render_generic_template(
            board_name="STM32 Nucleo-64",
            toolchain_name="Arduino",
            port=None,
            baud_rate=115200,
            compile_command="compile",
            upload_command="upload",
            monitor_command=None,
            boot_delay=3,
            board_info={},
            debug_tools=["openocd"],
            jtag_config=JtagConfig(interface="stlink", target="stm32f4x"),
        )
        assert "Permission denied" not in result

    def test_usb_path_unchanged_without_jtag_config(self):
        from edesto_dev.templates import render_generic_template
        result = render_generic_template(
            board_name="ESP32",
            toolchain_name="Arduino",
            port="/dev/ttyUSB0",
            baud_rate=115200,
            compile_command="compile",
            upload_command="upload",
            monitor_command=None,
            boot_delay=3,
            board_info={},
            debug_tools=[],
        )
        assert "connected via USB" in result
        assert "### Serial Output" in result
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_templates.py::TestJtagTemplateRendering -v`
Expected: FAIL — `TypeError: render_generic_template() got an unexpected keyword argument 'jtag_config'`

**Step 3: Write minimal implementation**

3a. Add `jtag_config` parameter to `render_generic_template`:

```python
def render_generic_template(
    board_name: str,
    toolchain_name: str,
    port: str | None,          # Changed: now optional (None for JTAG-only)
    baud_rate: int,
    compile_command: str,
    upload_command: str,
    monitor_command: str | None,
    boot_delay: int,
    board_info: dict,
    setup_info: str | None = None,
    debug_tools: list[str] | None = None,
    jtag_config: JtagConfig | None = None,
) -> str:
```

Add import at top of file:

```python
from edesto_dev.toolchain import Board, JtagConfig
```

3b. When `jtag_config` is set, force `"openocd"` into `debug_tools`:

```python
    tools = list(debug_tools or [])
    if jtag_config and "openocd" not in tools:
        tools.append("openocd")
```

3c. Pass `jtag_config` to `_generic_header`:

```python
    sections = [
        _generic_header(board_name, toolchain_name, port, baud_rate, jtag_config),
        ...
    ]
```

3d. Update `_generic_header` signature and body:

```python
def _generic_header(board_name: str, toolchain_name: str, port: str | None, baud_rate: int, jtag_config: JtagConfig | None = None) -> str:
    if jtag_config:
        lines = [f"# Embedded Development: {board_name}",
                 "",
                 f"You are developing firmware for a {board_name} connected via JTAG/SWD.",
                 "",
                 "## Hardware",
                 f"- Board: {board_name}",
                 f"- Debug probe: {jtag_config.interface}",
                 f"- Framework: {toolchain_name}",
                 f"- Upload: openocd (JTAG/SWD)"]
        if port:
            lines.append(f"- Serial port: {port}")
            lines.append(f"- Baud rate: {baud_rate}")
        return "\n".join(lines)
    return f"""# Embedded Development: {board_name}

You are developing firmware for a {board_name} connected via USB.

## Hardware
- Board: {board_name}
- Port: {port}
- Framework: {toolchain_name}
- Baud rate: {baud_rate}"""
```

3e. Update `_debugging` to skip serial section when `port` is None:

```python
def _debugging(port: str | None, baud_rate: int, boot_delay: int, debug_tools: list[str]) -> str:
    parts = []

    tool_guide = []
    if port:
        tool_guide.append(
            "- **Serial output** — application-level behavior (sensor readings, state machines, error messages)"
        )
    # ... rest unchanged ...

    # Serial subsection (only when port is available)
    if port:
        parts.append(_serial_section(port, baud_rate, boot_delay))

    # ... rest unchanged ...
```

3f. Update `_troubleshooting` to return empty when `port` is None:

```python
def _troubleshooting(port: str | None, baud_rate: int, boot_delay: int) -> str:
    if not port:
        return ""
    # ... existing body unchanged ...
```

3g. Update `render_from_toolchain` to pass through `jtag_config`:

```python
def render_from_toolchain(toolchain, board, port: str | None, debug_tools: list[str] | None = None, jtag_config: JtagConfig | None = None) -> str:
    ...
    return render_generic_template(
        ...
        debug_tools=debug_tools,
        jtag_config=jtag_config,
    )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_templates.py::TestJtagTemplateRendering -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `pytest tests/ -v`
Expected: All PASS (existing tests still pass because `jtag_config` defaults to `None`)

**Step 6: Commit**

```bash
git add edesto_dev/templates.py tests/test_templates.py
git commit -m "feat: add JTAG-aware template rendering"
```

---

### Task 4: Add `--upload jtag` flag and JTAG setup flow to CLI

**Files:**
- Modify: `edesto_dev/cli.py:20-147` (init command)
- Test: `tests/test_cli.py`

**Step 1: Write the failing tests**

In `tests/test_cli.py`, add:

```python
class TestInitJtag:
    @patch("edesto_dev.cli.detect_debug_tools", return_value=["openocd"])
    def test_upload_jtag_flag_prompts_for_setup(self, mock_debug, runner):
        """--upload jtag triggers JTAG setup flow."""
        with runner.isolated_filesystem():
            # Input: board choice (1=first), probe (1=ST-Link), target (accept default), serial? (n)
            user_input = "1\n1\n\nn\n"
            result = runner.invoke(main, ["init", "--board", "stm32-nucleo", "--upload", "jtag"], input=user_input)
            assert result.exit_code == 0
            assert Path("SKILLS.md").exists()
            content = Path("SKILLS.md").read_text()
            assert "JTAG" in content or "openocd" in content.lower()
            assert "stlink" in content.lower() or "stm32f4x" in content

    @patch("edesto_dev.cli.detect_debug_tools", return_value=["openocd"])
    def test_upload_jtag_with_serial_port(self, mock_debug, runner):
        """JTAG setup with serial port includes serial section."""
        with runner.isolated_filesystem():
            # Input: probe (1=ST-Link), target (accept default), serial? (y), port, baud
            user_input = "1\n\ny\n/dev/cu.usbmodem1103\n115200\n"
            result = runner.invoke(main, ["init", "--board", "stm32-nucleo", "--upload", "jtag"], input=user_input)
            assert result.exit_code == 0
            content = Path("SKILLS.md").read_text()
            assert "### Serial Output" in content
            assert "/dev/cu.usbmodem1103" in content

    @patch("edesto_dev.cli.detect_debug_tools", return_value=["openocd"])
    def test_upload_jtag_without_serial_port(self, mock_debug, runner):
        """JTAG setup without serial port omits serial section."""
        with runner.isolated_filesystem():
            # Input: probe (1=ST-Link), target (accept default), serial? (n)
            user_input = "1\n\nn\n"
            result = runner.invoke(main, ["init", "--board", "stm32-nucleo", "--upload", "jtag"], input=user_input)
            assert result.exit_code == 0
            content = Path("SKILLS.md").read_text()
            assert "### Serial Output" not in content

    @patch("edesto_dev.cli.detect_debug_tools", return_value=[])
    def test_upload_jtag_without_openocd_fails(self, mock_debug, runner):
        """--upload jtag fails if OpenOCD is not installed."""
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init", "--board", "stm32-nucleo", "--upload", "jtag"])
            assert result.exit_code != 0
            assert "openocd" in result.output.lower()

    @patch("edesto_dev.cli.detect_debug_tools", return_value=["openocd"])
    def test_upload_jtag_saves_edesto_toml(self, mock_debug, runner):
        """JTAG config is saved to edesto.toml."""
        with runner.isolated_filesystem():
            user_input = "1\n\nn\n"
            result = runner.invoke(main, ["init", "--board", "stm32-nucleo", "--upload", "jtag"], input=user_input)
            assert result.exit_code == 0
            assert Path("edesto.toml").exists()
            toml_content = Path("edesto.toml").read_text()
            assert "[jtag]" in toml_content
            assert "stlink" in toml_content

    @patch("edesto_dev.cli.detect_all_boards", return_value=[])
    @patch("edesto_dev.cli.detect_toolchain", return_value=None)
    @patch("edesto_dev.cli.detect_debug_tools", return_value=["openocd"])
    def test_auto_fallback_offers_jtag(self, mock_debug, mock_detect_tc, mock_detect_boards, runner):
        """When no USB boards found and OpenOCD installed, offer JTAG setup."""
        with runner.isolated_filesystem():
            # Input: yes to JTAG, pick board (e.g. "stm32-nucleo"), probe (1), target (default), serial? (n)
            user_input = "y\nstm32-nucleo\n1\n\nn\n"
            result = runner.invoke(main, ["init"], input=user_input)
            assert result.exit_code == 0
            assert Path("SKILLS.md").exists()
            content = Path("SKILLS.md").read_text()
            assert "JTAG" in content or "openocd" in content.lower()

    @patch("edesto_dev.cli.detect_all_boards", return_value=[])
    @patch("edesto_dev.cli.detect_toolchain", return_value=None)
    @patch("edesto_dev.cli.detect_debug_tools", return_value=["openocd"])
    def test_auto_fallback_jtag_declined_goes_to_custom(self, mock_debug, mock_detect_tc, mock_detect_boards, runner):
        """Declining JTAG falls through to custom manual setup."""
        with runner.isolated_filesystem():
            # Input: no to JTAG, then custom setup: compile, upload, baud, port, name
            user_input = "n\nmake build\nmake flash\n115200\n/dev/ttyUSB0\nMy Board\n"
            result = runner.invoke(main, ["init"], input=user_input)
            assert result.exit_code == 0
            content = Path("SKILLS.md").read_text()
            assert "make build" in content

    def test_upload_serial_is_default(self, runner):
        """--upload serial (or no --upload) uses the normal USB path."""
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init", "--board", "esp32", "--port", "/dev/ttyUSB0"])
            assert result.exit_code == 0
            content = Path("SKILLS.md").read_text()
            assert "connected via USB" in content
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py::TestInitJtag -v`
Expected: FAIL — `No such option: --upload`

**Step 3: Write minimal implementation**

Add `--upload` option to the init command:

```python
@click.option("--upload", "upload_method", type=click.Choice(["serial", "jtag"]), default=None, help="Upload method: serial (default) or jtag.")
def init(board, port, toolchain_name, upload_method):
```

Add imports at top of `cli.py`:

```python
from edesto_dev.toolchain import Board, JtagConfig
```

Add the JTAG constants for probes and a helper for the JTAG setup flow:

```python
_PROBES = [
    ("ST-Link", "stlink"),
    ("J-Link", "jlink"),
    ("CMSIS-DAP", "cmsis-dap"),
]


def _jtag_setup(board_def, toolchain):
    """Interactive JTAG setup. Returns (JtagConfig, port_or_None)."""
    # Pick probe
    click.echo("\nDebug probe:")
    for i, (name, _) in enumerate(_PROBES, 1):
        click.echo(f"  {i}. {name}")
    click.echo(f"  {len(_PROBES) + 1}. Other")
    probe_choice = click.prompt("Which probe?", type=int)
    if 1 <= probe_choice <= len(_PROBES):
        probe_name, probe_cfg = _PROBES[probe_choice - 1]
    else:
        probe_cfg = click.prompt("OpenOCD interface config name (without .cfg)")

    # Pick target
    default_target = board_def.openocd_target if board_def.openocd_target else None
    if default_target:
        target = click.prompt("OpenOCD target config", default=default_target)
    else:
        target = click.prompt("OpenOCD target config (e.g. stm32f4x, nrf52, esp32)")

    jtag_config = JtagConfig(interface=probe_cfg, target=target)

    # Serial port?
    if click.confirm("Do you have a serial port for monitoring?", default=False):
        port = click.prompt("Serial port")
        baud = click.prompt("Baud rate", type=int, default=board_def.baud_rate)
    else:
        port = None
        baud = board_def.baud_rate

    return jtag_config, port, baud
```

Then modify the init command body. The key changes:

**A. When `--upload jtag` is set:**

After resolving the board (but before generating SKILLS.md), check OpenOCD is installed and run the JTAG setup flow:

```python
    jtag_config = None
    if upload_method == "jtag":
        debug_tools = detect_debug_tools()
        if "openocd" not in debug_tools:
            click.echo("Error: OpenOCD is required for JTAG upload but was not found on PATH.")
            click.echo("Install OpenOCD: https://openocd.org/pages/getting-openocd.html")
            raise SystemExit(1)

        jtag_config, port, baud_rate = _jtag_setup(board_def, toolchain)

        # Build the OpenOCD upload command
        upload_cmd = f'openocd -f interface/{jtag_config.interface}.cfg -f target/{jtag_config.target}.cfg -c "program build/firmware.elf verify reset exit"'
```

**B. In the auto-detect fallback (no boards, no toolchain):**

Before the custom manual setup, check if OpenOCD is available and offer JTAG:

```python
        if not detected:
            if not toolchain:
                debug_tools = detect_debug_tools()
                if "openocd" in debug_tools:
                    click.echo("No boards detected via USB serial.")
                    if click.confirm("OpenOCD is installed — set up for JTAG/SWD flashing?", default=True):
                        # Ask for board
                        board_slug = click.prompt("Board slug (use 'edesto boards' to list, or 'custom')")
                        # ... resolve board_def and toolchain from slug ...
                        jtag_config, port, baud_rate = _jtag_setup(board_def, toolchain)
                        # ... continue to render ...
                    else:
                        # Fall through to existing custom manual setup
                        ...
```

**C. Generate SKILLS.md with JTAG config:**

When `jtag_config` is set, pass it to `render_from_toolchain`:

```python
    if jtag_config:
        debug_tools = detect_debug_tools()
        if "openocd" not in debug_tools:
            debug_tools.append("openocd")
        upload_cmd = f'openocd -f interface/{jtag_config.interface}.cfg -f target/{jtag_config.target}.cfg -c "program build/firmware.elf verify reset exit"'
        content = render_generic_template(
            board_name=board_def.name,
            toolchain_name=toolchain.name,
            port=port,
            baud_rate=baud_rate if port else board_def.baud_rate,
            compile_command=toolchain.compile_command(board_def),
            upload_command=upload_cmd,
            monitor_command=toolchain.monitor_command(board_def, port) if port else None,
            boot_delay=toolchain.serial_config(board_def).get("boot_delay", 3),
            board_info=toolchain.board_info(board_def),
            setup_info=toolchain.setup_info(board_def),
            debug_tools=debug_tools,
            jtag_config=jtag_config,
        )
    else:
        debug_tools = detect_debug_tools()
        content = render_from_toolchain(toolchain, board_def, port=port, debug_tools=debug_tools)
```

**D. Save JTAG config to edesto.toml:**

```python
    if jtag_config:
        toml_parts = [f'[jtag]\ninterface = "{jtag_config.interface}"\ntarget = "{jtag_config.target}"\n']
        if port:
            toml_parts.append(f'\n[serial]\nport = "{port}"\nbaud_rate = {baud_rate}\n')
        Path("edesto.toml").write_text("".join(toml_parts))
        click.echo("Saved JTAG configuration to edesto.toml")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py::TestInitJtag -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `pytest tests/ -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add edesto_dev/cli.py tests/test_cli.py
git commit -m "feat: add --upload jtag flag and JTAG setup flow to edesto init"
```

---

### Task 5: Final integration test and cleanup

**Files:**
- Test: `tests/test_cli.py`

**Step 1: Write the integration test**

Add to `tests/test_cli.py`:

```python
class TestInitJtagIntegration:
    @patch("edesto_dev.cli.detect_debug_tools", return_value=["openocd"])
    def test_full_jtag_workflow(self, mock_debug, runner):
        """Full JTAG init -> verify SKILLS.md + edesto.toml + copies."""
        with runner.isolated_filesystem():
            user_input = "1\n\nn\n"
            result = runner.invoke(main, ["init", "--board", "stm32-nucleo", "--upload", "jtag"], input=user_input)
            assert result.exit_code == 0

            # Verify SKILLS.md
            content = Path("SKILLS.md").read_text()
            assert "STM32 Nucleo-64" in content
            assert "JTAG" in content
            assert "stlink" in content.lower()
            assert "stm32f4x" in content
            assert "openocd" in content.lower()
            assert "### JTAG/SWD" in content
            assert "connected via USB" not in content

            # Verify copies
            assert Path("CLAUDE.md").read_text() == content
            assert Path(".cursorrules").read_text() == content
            assert Path("AGENTS.md").read_text() == content

            # Verify edesto.toml
            assert Path("edesto.toml").exists()
            toml = Path("edesto.toml").read_text()
            assert "stlink" in toml
            assert "stm32f4x" in toml
```

**Step 2: Run test**

Run: `pytest tests/test_cli.py::TestInitJtagIntegration -v`
Expected: PASS (if Tasks 1-4 are done correctly)

**Step 3: Run full test suite**

Run: `pytest tests/ -v`
Expected: All PASS

**Step 4: Commit**

```bash
git add tests/test_cli.py
git commit -m "test: add JTAG integration test"
```
