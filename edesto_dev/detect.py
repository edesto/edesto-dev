"""Project and board detection for edesto-dev."""

from pathlib import Path

from edesto_dev.toolchain import Toolchain, DetectedBoard
from edesto_dev.toolchains import list_toolchains


# Priority order for toolchain detection from project files.
_DETECTION_PRIORITY = ["platformio", "espidf", "arduino", "micropython"]


def detect_toolchain(path: Path) -> Toolchain | None:
    """Detect the toolchain from project files in the given directory.

    Checks for edesto.toml first (user override), then scans project
    files in priority order.
    """
    # 1. Check for edesto.toml override (will be implemented in Task 11)
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
    all_detected: list[DetectedBoard] = []
    for tc in list_toolchains():
        try:
            detected = tc.detect_boards()
            all_detected.extend(detected)
        except Exception:
            continue
    return all_detected


def _load_custom_toolchain(toml_path: Path) -> Toolchain | None:
    """Load a custom toolchain from edesto.toml. Returns None if not implemented yet."""
    # Will be implemented in Task 11 (Custom toolchain)
    return None
