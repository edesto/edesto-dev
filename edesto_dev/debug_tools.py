"""Debug tool detection for edesto-dev."""

import shutil


def _check_import(module_name: str) -> bool:
    """Check if a Python module can be imported."""
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False


def detect_debug_tools() -> list[str]:
    """Detect available debug tools. Returns list of tool names.

    Checks:
    - "saleae": logic2-automation Python package installed
    - "openocd": openocd binary on PATH
    - "scope": pyvisa Python package installed
    """
    tools: list[str] = []

    if _check_import("saleae"):
        tools.append("saleae")

    if shutil.which("openocd"):
        tools.append("openocd")

    if _check_import("pyvisa"):
        tools.append("scope")

    return tools
