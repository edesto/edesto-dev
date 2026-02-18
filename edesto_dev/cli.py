"""CLI entry point for edesto-dev."""

import glob as globmod
from pathlib import Path

import click

from edesto_dev.detect import detect_toolchain, detect_all_boards
from edesto_dev.toolchains import get_toolchain, list_toolchains
from edesto_dev.templates import render_from_toolchain


@click.group()
def main():
    """Set up AI coding agents for embedded development."""
    pass


@main.command()
@click.option("--board", type=str, help="Board slug (e.g. esp32, arduino-uno). Use 'edesto boards' to list.")
@click.option("--port", type=str, help="Serial port (e.g. /dev/ttyUSB0, /dev/cu.usbserial-0001).")
@click.option("--toolchain", "toolchain_name", type=str, help="Toolchain (e.g. arduino, platformio).")
def init(board, port, toolchain_name):
    """Generate a SKILLS.md for your board."""

    # Resolve toolchain
    if toolchain_name:
        toolchain = get_toolchain(toolchain_name)
        if not toolchain:
            click.echo(f"Error: Unknown toolchain: {toolchain_name}. Available: {', '.join(t.name for t in list_toolchains())}")
            raise SystemExit(1)
    else:
        toolchain = detect_toolchain(Path.cwd())

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
                # Ask user for custom commands
                click.echo("No toolchain detected and no boards found.")
                click.echo("Let's configure manually.\n")

                compile_cmd = click.prompt("What command compiles your firmware?")
                upload_cmd = click.prompt("What command uploads to the board?")
                baud = click.prompt("What baud rate does your board use?", type=int, default=115200)
                port = click.prompt("What serial port is your board on?")
                board_name = click.prompt("What is your board called?", default="Custom Board")

                # Create custom toolchain
                from edesto_dev.toolchains.custom import CustomToolchain
                from edesto_dev.toolchain import Board
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

    content = render_from_toolchain(toolchain, board_def, port=port)

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

    if ok:
        click.echo("\nAll checks passed. Ready for embedded development.")
    else:
        click.echo("\nSome checks failed. Fix the issues above.")
