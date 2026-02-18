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
