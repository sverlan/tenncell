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
    "ObservedSignal",
    "ObservedSignalKind",
    "VerilogObservation",
]

_OBSERVATION_NAMES = {"ObservedSignal", "ObservedSignalKind", "VerilogObservation"}


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
    if name in _OBSERVATION_NAMES:
        return getattr(import_module(".generation.observation", __name__), name)
    raise AttributeError(name)
