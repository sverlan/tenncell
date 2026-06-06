"""Verilog backend helpers for TENNCell transformers."""

from importlib import import_module

__all__ = [
    "ClockConfig",
    "ExternalInstance",
    "ExternalModuleSchema",
    "VerilogEncoding",
    "PortConfig",
    "RealEncoding",
    "VerilogFixedPointEncoding",
    "VerilogLogicEncoding",
    "ResetConfig",
    "VerilogHardwareConfig",
]


def __getattr__(name: str):
    if name in {
        "ClockConfig",
        "ExternalInstance",
        "ExternalModuleSchema",
        "VerilogEncoding",
        "PortConfig",
        "RealEncoding",
        "VerilogFixedPointEncoding",
        "VerilogLogicEncoding",
        "ResetConfig",
        "VerilogHardwareConfig",
    }:
        return getattr(import_module(".hardware_config", __name__), name)
    raise AttributeError(name)
