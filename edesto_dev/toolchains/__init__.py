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


# Auto-import toolchain modules so they self-register.
from edesto_dev.toolchains import arduino as _arduino  # noqa: F401, E402
from edesto_dev.toolchains import platformio as _platformio  # noqa: F401, E402
from edesto_dev.toolchains import espidf as _espidf  # noqa: F401, E402
from edesto_dev.toolchains import micropython as _micropython  # noqa: F401, E402
from edesto_dev.toolchains import zephyr as _zephyr  # noqa: F401, E402
from edesto_dev.toolchains import cmake_native as _cmake_native  # noqa: F401, E402
# Note: custom is NOT imported here — it's created on demand from edesto.toml
