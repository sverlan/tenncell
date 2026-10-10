"""Resolved Verilog encodings used during backend generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, TypeAlias

if TYPE_CHECKING:
    from .conversions import VerilogConversionEmitter


@dataclass(slots=True)
class VerilogLogicEncoding:
    """Resolved Verilog encoding for a logic or packed-vector value."""

    kind: Literal["logic"]
    width: int
    signed: bool = False


@dataclass(slots=True)
class VerilogFixedPointEncoding:
    """Resolved Verilog encoding for a fixed-point value."""

    kind: Literal["fixed"]
    width: int
    signed: bool = False
    frac_bits: int = 0


VerilogEncoding: TypeAlias = VerilogLogicEncoding | VerilogFixedPointEncoding


def encoding_from_parts(
    emitter: VerilogConversionEmitter | None,
    kind: str,
    width: int,
    signed: bool,
    frac_bits: int,
) -> VerilogEncoding:
    """Build one resolved encoding object from primitive fields.

    ``emitter`` is unused; it is kept for the mixin call convention.
    """
    if kind == "fixed":
        return VerilogFixedPointEncoding(
            kind="fixed",
            width=width,
            signed=signed,
            frac_bits=frac_bits,
        )
    return VerilogLogicEncoding(kind="logic", width=width, signed=signed)


def type_info_encoding(emitter: VerilogConversionEmitter, type_info):
    """Convert a Verilog type hint into a lowering encoding object."""
    from ..hardware_config import VerilogLogicTypeInfo

    if isinstance(type_info, VerilogLogicTypeInfo):
        return VerilogLogicEncoding(
            kind="logic",
            width=type_info.width,
            signed=type_info.signed,
        )
    return VerilogFixedPointEncoding(
        kind="fixed",
        width=type_info.width,
        signed=type_info.signed,
        frac_bits=type_info.frac_bits,
    )


def type_info_decl(emitter: VerilogConversionEmitter, type_info) -> str:
    """Return the Verilog storage declaration for a typed variable."""
    from ..hardware_config import VerilogLogicTypeInfo

    if isinstance(type_info, VerilogLogicTypeInfo):
        return emitter._type_decl("logic", type_info.width, type_info.signed)
    return emitter._type_decl("fixed", type_info.width, type_info.signed)
