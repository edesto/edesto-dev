"""CLI entry point for edesto-dev."""

import glob as globmod
from pathlib import Path

import click

from edesto_dev.debug_tools import detect_debug_tools
from edesto_dev.detect import detect_toolchain, detect_all_boards
from edesto_dev.toolchains import get_toolchain, list_toolchains
from edesto_dev.toolchain import Board, JtagConfig
from edesto_dev.templates import render_from_toolchain, render_generic_template


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
    """Write SKILLS.md and copies, handling overwrite confirmation."""
    skills_path = Path("SKILLS.md")
    copies = [Path("CLAUDE.md"), Path(".cursorrules"), Path("AGENTS.md")]

    if skills_path.exists():
        if not click.confirm("SKILLS.md already exists. Overwrite?"):
            click.echo("Aborted.")
            return

    skills_path.write_text(content)
    for copy_path in copies:
        copy_path.write_text(content)

    if port:
        click.echo(f"Generated SKILLS.md for {board_def.name} on {port}. Also created: CLAUDE.md, .cursorrules, AGENTS.md")
    else:
        click.echo(f"Generated SKILLS.md for {board_def.name} (JTAG/SWD). Also created: CLAUDE.md, .cursorrules, AGENTS.md")


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
        _save_jtag_toml(jtag_config, port, baud_rate)
        _write_skills_files(content, board_def, port)
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
                        _save_jtag_toml(jtag_config, port, baud_rate)
                        _write_skills_files(content, board_def, port)
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
