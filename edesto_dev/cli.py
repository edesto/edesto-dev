"""CLI entry point for edesto-dev."""

import glob as globmod
import json as jsonmod
from pathlib import Path

import click

from edesto_dev.debug_tools import detect_debug_tools
from edesto_dev.detect import detect_toolchain, detect_all_boards
from edesto_dev.toolchains import get_toolchain, list_toolchains
from edesto_dev.toolchain import Board, JtagConfig
from edesto_dev.templates import render_from_toolchain, render_generic_template
from edesto_dev.config import (
    load_project_config, get_config_value, set_config_value, list_config,
    ensure_edesto_dir, load_scan_cache, save_scan_cache, clear_debug_state,
)
from edesto_dev.serial.port import list_serial_ports, open_serial, resolve_port_and_baud, SerialError
from edesto_dev.serial.reader import serial_read, serial_send, serial_monitor
from edesto_dev.serial.parser import LineParser, ParserConfig
from edesto_dev.debug.scan import scan_project


@click.group()
def main():
    """Set up AI coding agents for embedded development."""
    pass


_PROBES = [
    ("ST-Link", "stlink"),
    ("J-Link", "jlink"),
    ("CMSIS-DAP", "cmsis-dap"),
]


def _jtag_setup(board_def):
    """Interactive JTAG probe/target setup. Returns (JtagConfig, port_or_None, baud_rate)."""
    click.echo("\nDebug probe:")
    for i, (name, _) in enumerate(_PROBES, 1):
        click.echo(f"  {i}. {name}")
    click.echo(f"  {len(_PROBES) + 1}. Other")
    probe_choice = click.prompt("Which probe?", type=int)
    if 1 <= probe_choice <= len(_PROBES):
        _, probe_cfg = _PROBES[probe_choice - 1]
    else:
        probe_cfg = click.prompt("OpenOCD interface config name (without .cfg)")

    default_target = board_def.openocd_target if board_def.openocd_target else None
    if default_target:
        target = click.prompt("OpenOCD target config", default=default_target)
    else:
        target = click.prompt("OpenOCD target config (e.g. stm32f4x, nrf52, esp32)")

    jtag_config = JtagConfig(interface=probe_cfg, target=target)

    if click.confirm("Do you have a serial port for monitoring?", default=False):
        port = click.prompt("Serial port")
        baud = click.prompt("Baud rate", type=int, default=board_def.baud_rate)
    else:
        port = None
        baud = board_def.baud_rate

    return jtag_config, port, baud


def _render_jtag_content(board_def, toolchain, jtag_config, port, baud_rate):
    """Render SKILLS.md content for a JTAG setup."""
    debug_tools = detect_debug_tools()
    if "openocd" not in debug_tools:
        debug_tools.append("openocd")
    upload_cmd = f'openocd -f interface/{jtag_config.interface}.cfg -f target/{jtag_config.target}.cfg -c "program build/firmware.elf verify reset exit"'
    return render_generic_template(
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


def _save_jtag_toml(jtag_config, port=None, baud_rate=None):
    """Save JTAG config to edesto.toml."""
    toml_parts = [f'[jtag]\ninterface = "{jtag_config.interface}"\ntarget = "{jtag_config.target}"\n']
    if port:
        toml_parts.append(f'\n[serial]\nport = "{port}"\nbaud_rate = {baud_rate}\n')
    Path("edesto.toml").write_text("".join(toml_parts))
    click.echo("Saved JTAG configuration to edesto.toml")


def _write_skills_files(content, board_def, port):
    """Write SKILLS.md and copies, handling overwrite confirmation. Returns True if written."""
    skills_path = Path("SKILLS.md")
    copies = [Path("CLAUDE.md"), Path(".cursorrules"), Path("AGENTS.md")]

    if skills_path.exists():
        if not click.confirm("SKILLS.md already exists. Overwrite?"):
            click.echo("Aborted.")
            return False

    skills_path.write_text(content)
    for copy_path in copies:
        copy_path.write_text(content)

    if port:
        click.echo(f"Generated SKILLS.md for {board_def.name} on {port}. Also created: CLAUDE.md, .cursorrules, AGENTS.md")
    else:
        click.echo(f"Generated SKILLS.md for {board_def.name} (JTAG/SWD). Also created: CLAUDE.md, .cursorrules, AGENTS.md")
    return True


@main.command()
@click.option("--board", type=str, help="Board slug (e.g. esp32, arduino-uno). Use 'edesto boards' to list.")
@click.option("--port", type=str, help="Serial port (e.g. /dev/ttyUSB0, /dev/cu.usbserial-0001).")
@click.option("--toolchain", "toolchain_name", type=str, help="Toolchain (e.g. arduino, platformio).")
@click.option("--upload", "upload_method", type=click.Choice(["serial", "jtag"]), default=None, help="Upload method: serial (default) or jtag.")
def init(board, port, toolchain_name, upload_method):
    """Generate a SKILLS.md for your board."""

    # Resolve toolchain
    if toolchain_name:
        toolchain = get_toolchain(toolchain_name)
        if not toolchain:
            click.echo(f"Error: Unknown toolchain: {toolchain_name}. Available: {', '.join(t.name for t in list_toolchains())}")
            raise SystemExit(1)
    else:
        toolchain = detect_toolchain(Path.cwd())

    # ---- JTAG early path ----
    if upload_method == "jtag":
        debug_tools = detect_debug_tools()
        if "openocd" not in debug_tools:
            click.echo("Error: OpenOCD is required for JTAG upload but was not found on PATH.")
            click.echo("Install OpenOCD: https://openocd.org/pages/getting-openocd.html")
            raise SystemExit(1)

        if not board:
            click.echo("Error: --board is required for JTAG upload.")
            raise SystemExit(1)

        # Resolve board_def and toolchain
        if toolchain:
            board_def = toolchain.get_board(board)
        else:
            board_def = None
            for tc in list_toolchains():
                board_def = tc.get_board(board)
                if board_def:
                    toolchain = tc
                    break
        if not board_def:
            click.echo(f"Error: Unknown board: {board}. Use 'edesto boards' to list supported boards.")
            raise SystemExit(1)

        jtag_config, port, baud_rate = _jtag_setup(board_def)
        content = _render_jtag_content(board_def, toolchain, jtag_config, port, baud_rate)
        if _write_skills_files(content, board_def, port):
            _save_jtag_toml(jtag_config, port, baud_rate)
        return

    # ---- Existing USB serial path ----

    # Resolve board and port
    if board and port:
        # Both provided -- find board in toolchain
        if toolchain:
            board_def = toolchain.get_board(board)
        else:
            # No toolchain detected, search all toolchains for this board
            board_def = None
            for tc in list_toolchains():
                board_def = tc.get_board(board)
                if board_def:
                    toolchain = tc
                    break
        if not board_def:
            click.echo(f"Error: Unknown board: {board}. Use 'edesto boards' to list supported boards.")
            raise SystemExit(1)
    elif board and not port:
        # Board specified, detect port
        if not toolchain:
            for tc in list_toolchains():
                board_def = tc.get_board(board)
                if board_def:
                    toolchain = tc
                    break
            if not toolchain:
                click.echo(f"Error: Unknown board: {board}.")
                raise SystemExit(1)
        else:
            board_def = toolchain.get_board(board)
            if not board_def:
                click.echo(f"Error: Unknown board: {board}.")
                raise SystemExit(1)
        detected = toolchain.detect_boards()
        matches = [d for d in detected if d.board.slug == board]
        if matches:
            port = matches[0].port
            click.echo(f"Detected {board_def.name} on {port}")
        else:
            click.echo(f"Error: Could not detect port for {board}. Specify with --port.")
            raise SystemExit(1)
    elif not board and not port:
        # Full auto-detection
        detected = detect_all_boards()
        if not detected:
            if not toolchain:
                # No toolchain from project files, no boards from USB
                # Check for OpenOCD and offer JTAG setup
                debug_tools = detect_debug_tools()
                if "openocd" in debug_tools:
                    click.echo("No boards detected via USB serial.")
                    if click.confirm("OpenOCD is installed \u2014 set up for JTAG/SWD flashing?", default=True):
                        board_slug = click.prompt("Board slug (use 'edesto boards' to list)")
                        board_def = None
                        for tc in list_toolchains():
                            board_def = tc.get_board(board_slug)
                            if board_def:
                                toolchain = tc
                                break
                        if not board_def:
                            click.echo(f"Error: Unknown board: {board_slug}")
                            raise SystemExit(1)

                        jtag_config, port, baud_rate = _jtag_setup(board_def)
                        content = _render_jtag_content(board_def, toolchain, jtag_config, port, baud_rate)
                        if _write_skills_files(content, board_def, port):
                            _save_jtag_toml(jtag_config, port, baud_rate)
                        return
                    # else: fall through to custom manual setup

                # Custom manual setup
                click.echo("No toolchain detected and no boards found.")
                click.echo("Let's configure manually.\n")

                compile_cmd = click.prompt("What command compiles your firmware?")
                upload_cmd = click.prompt("What command uploads to the board?")
                baud = click.prompt("What baud rate does your board use?", type=int, default=115200)
                port = click.prompt("What serial port is your board on?")
                board_name = click.prompt("What is your board called?", default="Custom Board")

                # Create custom toolchain
                from edesto_dev.toolchains.custom import CustomToolchain
                toolchain = CustomToolchain(compile_cmd=compile_cmd, upload_cmd=upload_cmd, baud_rate=baud)
                board_def = Board(slug="custom", name=board_name, baud_rate=baud)

                # Save to edesto.toml
                toml_content = f'[toolchain]\nname = "custom"\ncompile = "{compile_cmd}"\nupload = "{upload_cmd}"\n\n[serial]\nbaud_rate = {baud}\nport = "{port}"\n'
                Path("edesto.toml").write_text(toml_content)
                click.echo(f"\nSaved configuration to edesto.toml")
            else:
                # Toolchain detected from files but no boards on USB
                click.echo("Error: No boards detected. Is a board connected via USB?")
                click.echo("You can specify manually: edesto init --board <board> --port <port>")
                raise SystemExit(1)
        elif len(detected) == 1:
            board_def = detected[0].board
            port = detected[0].port
            toolchain_name = detected[0].toolchain_name
            if not toolchain:
                toolchain = get_toolchain(toolchain_name)
            click.echo(f"Detected {board_def.name} on {port}")
        else:
            click.echo("Multiple boards detected:\n")
            for i, d in enumerate(detected, 1):
                click.echo(f"  {i}. {d.board.name} on {d.port}")
            click.echo()
            choice = click.prompt("Which board?", type=int)
            if choice < 1 or choice > len(detected):
                click.echo("Invalid choice.")
                raise SystemExit(1)
            board_def = detected[choice - 1].board
            port = detected[choice - 1].port
            if not toolchain:
                toolchain = get_toolchain(detected[choice - 1].toolchain_name)
    else:
        # port specified but not board
        click.echo("Error: --board is required when using --port.")
        raise SystemExit(1)

    debug_tools = detect_debug_tools()
    content = render_from_toolchain(toolchain, board_def, port=port, debug_tools=debug_tools)

    skills_path = Path("SKILLS.md")
    copies = [Path("CLAUDE.md"), Path(".cursorrules"), Path("AGENTS.md")]

    if skills_path.exists():
        if not click.confirm("SKILLS.md already exists. Overwrite?"):
            click.echo("Aborted.")
            return

    skills_path.write_text(content)
    for copy_path in copies:
        copy_path.write_text(content)

    click.echo(f"Generated SKILLS.md for {board_def.name} on {port}. Also created: CLAUDE.md, .cursorrules, AGENTS.md")

    # Ensure .edesto/ in .gitignore
    _update_gitignore()


def _update_gitignore():
    """Append .edesto/ to .gitignore if not already present."""
    gitignore = Path(".gitignore")
    if gitignore.exists():
        content = gitignore.read_text()
        if ".edesto/" not in content:
            gitignore.write_text(content.rstrip() + "\n.edesto/\n")
    else:
        gitignore.write_text(".edesto/\n")


@main.command()
@click.option("--toolchain", "toolchain_name", type=str, help="Filter by toolchain.")
def boards(toolchain_name):
    """List supported boards."""
    if toolchain_name:
        tc = get_toolchain(toolchain_name)
        if not tc:
            click.echo(f"Error: Unknown toolchain: {toolchain_name}")
            raise SystemExit(1)
        toolchain_list = [tc]
    else:
        toolchain_list = list_toolchains()

    total = sum(len(tc.list_boards()) for tc in toolchain_list)
    click.echo(f"Supported boards ({total}):\n")
    for tc in toolchain_list:
        tc_boards = tc.list_boards()
        if tc_boards:
            click.echo(f"  {tc.name}:")
            for b in tc_boards:
                click.echo(f"    {b.slug:<20} {b.name}")
            click.echo()


@main.command()
def doctor():
    """Check your environment for embedded development."""
    ok = True

    # Check each toolchain
    for tc in list_toolchains():
        result = tc.doctor()
        if result["ok"]:
            click.echo(f"[OK] {tc.name}: {result['message']}")
        else:
            click.echo(f"[!!] {tc.name}: {result['message']}")
            ok = False

    # Check serial ports
    ports = globmod.glob("/dev/ttyUSB*") + globmod.glob("/dev/ttyACM*") + globmod.glob("/dev/cu.usb*")
    if ports:
        click.echo("[OK] Serial ports found:")
        for p in ports:
            click.echo(f"     {p}")
    else:
        click.echo("[!!] No serial ports detected. Is a board connected via USB?")
        ok = False

    # Check Python serial
    try:
        import serial
        click.echo(f"[OK] pyserial installed: {serial.__version__}")
    except ImportError:
        click.echo("[!!] pyserial not installed. Run: pip install pyserial")
        ok = False

    # Check debug tools (optional)
    debug_tools = detect_debug_tools()
    click.echo("\nDebug tools (optional):")
    _TOOL_NAMES = {"saleae": "Saleae Logic 2 (logic2-automation)", "openocd": "OpenOCD (JTAG/SWD)", "scope": "Oscilloscope (pyvisa)"}
    for tool_id, tool_name in _TOOL_NAMES.items():
        if tool_id in debug_tools:
            click.echo(f"  [OK] {tool_name}")
        else:
            click.echo(f"  [--] {tool_name} — not installed")

    if ok:
        click.echo("\nAll checks passed. Ready for embedded development.")
    else:
        click.echo("\nSome checks failed. Fix the issues above.")


# ---------------------------------------------------------------------------
# Serial command group
# ---------------------------------------------------------------------------

@main.group()
def serial():
    """Serial port communication tools."""
    pass


@serial.command("ports")
@click.option("--json", "use_json", is_flag=True, help="Output JSON.")
def serial_ports_cmd(use_json):
    """List available serial ports."""
    ports = list_serial_ports()
    if use_json:
        data = [{"device": p.device, "description": p.description, "hwid": p.hwid, "board_label": p.board_label} for p in ports]
        click.echo(jsonmod.dumps(data, indent=2))
    else:
        if not ports:
            click.echo("No serial ports found.")
            return
        for p in ports:
            label = f" ({p.board_label})" if p.board_label else ""
            click.echo(f"  {p.device:<25} {p.description}{label}")


@serial.command("read")
@click.option("--port", type=str, help="Serial port.")
@click.option("--baud", type=int, help="Baud rate.")
@click.option("--duration", type=float, default=10, help="Read duration in seconds.")
@click.option("--until", type=str, help="Stop when this string appears.")
@click.option("--json", "use_json", is_flag=True, help="Output JSON.")
def serial_read_cmd(port, baud, duration, until, use_json):
    """Read serial output from the board."""
    project_dir = Path.cwd()
    try:
        port, baud = resolve_port_and_baud(port, baud, project_dir)
    except Exception as e:
        if use_json:
            click.echo(jsonmod.dumps({"error": str(e)}), err=True)
        else:
            click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    try:
        ser = open_serial(port, baud)
    except SerialError as e:
        if use_json:
            click.echo(jsonmod.dumps(e.to_dict()), err=True)
        else:
            click.echo(f"Error: {e.message}", err=True)
        raise SystemExit(e.exit_code)

    # Load or run scan for parser config
    ensure_edesto_dir(project_dir)
    log_path = project_dir / ".edesto" / "debug-log.jsonl"
    scan_cache = load_scan_cache(project_dir)
    if scan_cache:
        parser = LineParser(ParserConfig.from_scan_cache(scan_cache))
    else:
        parser = LineParser()
        # Background scan
        import threading

        def bg_scan():
            try:
                result = scan_project(project_dir)
                save_scan_cache(project_dir, result.to_dict())
            except Exception:
                pass
        threading.Thread(target=bg_scan, daemon=True).start()

    try:
        result = serial_read(
            ser, duration=duration, until=until,
            parser=parser, log_path=log_path,
            quiet_timeout=0.5 if not until else None,
        )
    finally:
        ser.close()

    if use_json:
        click.echo(jsonmod.dumps({
            "lines": result.lines,
            "duration_seconds": result.duration_seconds,
            "exit_reason": result.exit_reason,
        }, indent=2))
    else:
        for line in result.lines:
            click.echo(line)


@serial.command("send")
@click.argument("command")
@click.option("--port", type=str, help="Serial port.")
@click.option("--baud", type=int, help="Baud rate.")
@click.option("--timeout", type=float, default=10, help="Response timeout in seconds.")
@click.option("--until", type=str, help="Stop when this string appears.")
@click.option("--no-wait", is_flag=True, help="Don't wait for response.")
@click.option("--json", "use_json", is_flag=True, help="Output JSON.")
def serial_send_cmd(command, port, baud, timeout, until, no_wait, use_json):
    """Send a command to the board and read response."""
    project_dir = Path.cwd()
    try:
        port, baud = resolve_port_and_baud(port, baud, project_dir)
    except Exception as e:
        if use_json:
            click.echo(jsonmod.dumps({"error": str(e)}), err=True)
        else:
            click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    try:
        ser = open_serial(port, baud)
    except SerialError as e:
        if use_json:
            click.echo(jsonmod.dumps(e.to_dict()), err=True)
        else:
            click.echo(f"Error: {e.message}", err=True)
        raise SystemExit(e.exit_code)

    # Load scan cache for markers/echo/terminator
    ensure_edesto_dir(project_dir)
    log_path = project_dir / ".edesto" / "debug-log.jsonl"
    scan_cache = load_scan_cache(project_dir)

    success_markers = []
    error_markers = []
    strip_echo = False
    line_terminator = "\n"
    wait_ready = None
    parser = LineParser()

    if scan_cache:
        serial_data = scan_cache.get("serial", {})
        success_markers = serial_data.get("success_markers", [])
        error_markers = serial_data.get("error_markers", [])
        strip_echo = serial_data.get("echo", False)
        line_terminator = serial_data.get("line_terminator", "\n")
        wait_ready = serial_data.get("boot_marker")
        parser = LineParser(ParserConfig.from_scan_cache(scan_cache))

    try:
        result = serial_send(
            ser, command,
            line_terminator=line_terminator,
            wait_ready=wait_ready,
            ready_timeout=5,
            strip_echo=strip_echo,
            until=until,
            success_markers=success_markers,
            error_markers=error_markers,
            quiet_timeout=0.5,
            parser=parser,
            log_path=log_path,
            timeout=timeout,
        )
    finally:
        ser.close()

    if use_json:
        click.echo(jsonmod.dumps({
            "lines": result.lines,
            "duration_seconds": result.duration_seconds,
            "exit_reason": result.exit_reason,
            "exit_code": result.exit_code,
            "was_error": result.was_error,
        }, indent=2))
    else:
        for line in result.lines:
            click.echo(line)

    raise SystemExit(result.exit_code)


@serial.command("monitor")
@click.option("--port", type=str, help="Serial port.")
@click.option("--baud", type=int, help="Baud rate.")
@click.option("--duration", type=float, help="Monitor duration in seconds.")
@click.option("--json", "use_json", is_flag=True, help="Output JSON lines.")
def serial_monitor_cmd(port, baud, duration, use_json):
    """Stream serial output continuously."""
    project_dir = Path.cwd()
    try:
        port, baud = resolve_port_and_baud(port, baud, project_dir)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    try:
        ser = open_serial(port, baud)
    except SerialError as e:
        click.echo(f"Error: {e.message}", err=True)
        raise SystemExit(e.exit_code)

    ensure_edesto_dir(project_dir)
    log_path = project_dir / ".edesto" / "debug-log.jsonl"
    scan_cache = load_scan_cache(project_dir)
    parser = LineParser(ParserConfig.from_scan_cache(scan_cache)) if scan_cache else LineParser()

    try:
        serial_monitor(ser, duration=duration, parser=parser, log_path=log_path)
    finally:
        ser.close()


# ---------------------------------------------------------------------------
# Debug command group
# ---------------------------------------------------------------------------

@main.group()
def debug():
    """Debug tools for firmware development."""
    pass


@debug.command("scan")
@click.option("--path", type=click.Path(exists=True), help="Scan a specific path.")
@click.option("--json", "use_json", is_flag=True, help="Output JSON.")
def debug_scan_cmd(path, use_json):
    """Scan project source files for debug patterns."""
    project_dir = Path.cwd()
    ensure_edesto_dir(project_dir)
    scan_path = Path(path) if path else None
    result = scan_project(project_dir, path=scan_path)
    save_scan_cache(project_dir, result.to_dict())

    if use_json:
        click.echo(jsonmod.dumps(result.to_dict(), indent=2))
    else:
        click.echo("Debug scan complete.")
        api = result.logging_api.get("primary")
        if api:
            click.echo(f"  Logging API: {api}")
        boot = result.serial.get("boot_marker")
        if boot:
            click.echo(f"  Boot marker: {boot}")
        baud = result.serial.get("baud_rate")
        if baud:
            click.echo(f"  Baud rate: {baud}")
        if result.danger_zones:
            click.echo(f"  Danger zones: {len(result.danger_zones)}")
        if result.safe_zones:
            click.echo(f"  Safe zones: {len(result.safe_zones)}")
        cmds = result.serial.get("known_commands", [])
        if cmds:
            click.echo(f"  Known commands: {', '.join(c['command'] for c in cmds)}")
        click.echo(f"  Saved to .edesto/debug-scan.json")


@debug.command("instrument")
@click.argument("file_line", required=False)
@click.option("--expr", multiple=True, help="Expression to log.")
@click.option("--fmt", multiple=True, help="Format specifier for each expression.")
@click.option("--function", "func_name", type=str, help="Function name for entry/exit logging.")
@click.option("--gpio", "gpio_file_line", type=str, help="FILE:LINE for GPIO toggle.")
@click.option("--force", is_flag=True, help="Override danger zone check.")
def debug_instrument_cmd(file_line, expr, fmt, func_name, gpio_file_line, force):
    """Insert debug instrumentation into source files."""
    from edesto_dev.debug.instrument import (
        instrument_line, instrument_function, instrument_gpio,
        InstrumentManifest,
    )
    from edesto_dev.config import load_scan_cache, save_instrument_manifest, load_instrument_manifest

    project_dir = Path.cwd()
    ensure_edesto_dir(project_dir)

    # Load or create manifest
    manifest_data = load_instrument_manifest(project_dir)
    manifest = InstrumentManifest.from_dict(manifest_data) if manifest_data else InstrumentManifest()

    # Determine logging API from scan cache
    scan_cache = load_scan_cache(project_dir)
    logging_api = "printf"
    if scan_cache:
        api = scan_cache.get("logging_api", {}).get("primary")
        if api:
            logging_api = api

    try:
        if gpio_file_line:
            filepath, line = _parse_file_line(gpio_file_line)
            config = load_project_config(project_dir)
            gpio_pin = config.debug.gpio
            instrument_gpio(filepath, line, gpio_pin=gpio_pin, manifest=manifest)
            click.echo(f"Inserted GPIO toggle at {filepath}:{line}")
        elif func_name:
            # Find the file containing the function
            scan_cache = load_scan_cache(project_dir)
            filepath = _find_function_file(project_dir, func_name)
            instrument_function(filepath, func_name, logging_api=logging_api, manifest=manifest)
            click.echo(f"Inserted entry/exit logging for {func_name}")
        elif file_line:
            filepath, line = _parse_file_line(file_line)
            fmts = list(fmt) if fmt else None
            instrument_line(
                filepath, line, exprs=list(expr), fmts=fmts,
                logging_api=logging_api, manifest=manifest,
                project_dir=project_dir, force=force,
            )
            click.echo(f"Inserted debug print at {filepath}:{line}")
        else:
            click.echo("Usage: edesto debug instrument <FILE:LINE> --expr <EXPR> [--fmt <FMT>]")
            return
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    save_instrument_manifest(project_dir, manifest.to_dict())


@debug.command("clean")
@click.option("--dry-run", is_flag=True, help="Show what would be removed.")
@click.option("--file", "file_path", type=click.Path(), help="Clean a specific file.")
def debug_clean_cmd(dry_run, file_path):
    """Remove all debug instrumentation."""
    from edesto_dev.debug.instrument import clean_all

    project_dir = Path.cwd()
    file_arg = Path(file_path) if file_path else None
    result = clean_all(project_dir, file=file_arg, dry_run=dry_run)

    if dry_run:
        click.echo(f"Would remove {result.removed_count} instrumented lines:")
        for line in result.removed_lines:
            click.echo(f"  {line}")
    else:
        click.echo(f"Removed {result.removed_count} instrumented lines.")
    if result.orphan_warnings:
        for warning in result.orphan_warnings:
            click.echo(f"Warning: {warning}")


@debug.command("reset")
def debug_reset_cmd():
    """Clear all debug state files."""
    project_dir = Path.cwd()
    clear_debug_state(project_dir)
    click.echo("Debug state cleared.")


@debug.command("status")
@click.option("--json", "use_json", is_flag=True, help="Output JSON.")
@click.option("--port", type=str, help="Serial port.")
@click.option("--baud", type=int, help="Baud rate.")
def debug_status_cmd(use_json, port, baud):
    """Show debug diagnostic snapshot."""
    from edesto_dev.debug.status import collect_status

    project_dir = Path.cwd()
    status = collect_status(project_dir, port=port, baud=baud)

    if use_json:
        click.echo(jsonmod.dumps(status.to_dict(), indent=2))
    else:
        click.echo(status.to_human())


# ---------------------------------------------------------------------------
# Config command
# ---------------------------------------------------------------------------

def _parse_file_line(file_line: str) -> tuple[Path, int]:
    """Parse FILE:LINE argument into (Path, int)."""
    parts = file_line.rsplit(":", 1)
    if len(parts) != 2:
        raise click.UsageError(f"Expected FILE:LINE format, got: {file_line}")
    try:
        return Path(parts[0]), int(parts[1])
    except ValueError:
        raise click.UsageError(f"Line number must be an integer, got: {parts[1]}")


def _find_function_file(project_dir: Path, func_name: str) -> Path:
    """Find the source file containing a function definition."""
    import re
    pattern = re.compile(rf"\b{re.escape(func_name)}\s*\(")
    source_exts = {".c", ".cpp", ".h", ".hpp", ".ino"}
    skip_dirs = {"build", ".pio", ".git", "node_modules", ".edesto"}
    for filepath in project_dir.rglob("*"):
        if not filepath.is_file() or filepath.suffix not in source_exts:
            continue
        if any(part in skip_dirs for part in filepath.relative_to(project_dir).parts):
            continue
        content = filepath.read_text(errors="ignore")
        if pattern.search(content):
            return filepath
    raise click.UsageError(f"Function '{func_name}' not found in project source files.")


@main.command("config")
@click.argument("key", required=False)
@click.argument("value", required=False)
@click.option("--list", "show_list", is_flag=True, help="Show all config values.")
def config_cmd(key, value, show_list):
    """Get or set edesto.toml configuration values."""
    project_dir = Path.cwd()

    if show_list:
        values = list_config(project_dir)
        if not values:
            click.echo("No configuration found.")
            return
        for k, v in sorted(values.items()):
            click.echo(f"  {k} = {v}")
        return

    if key and value:
        set_config_value(project_dir, key, value)
        click.echo(f"Set {key} = {value}")
        return

    if key:
        val = get_config_value(project_dir, key)
        if val is None:
            click.echo(f"{key} is not set.")
        else:
            click.echo(f"{key} = {val}")
        return

    click.echo("Usage: edesto config <KEY> [VALUE] or edesto config --list")
