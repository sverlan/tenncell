"""Verilog literal lowering helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..hardware_config import VerilogEncoding

if TYPE_CHECKING:
    from .conversions import VerilogConversionEmitter
    from .context import VerilogEmissionContext


def fixed_storage_decl(
    emitter: VerilogConversionEmitter, width: int, signed: bool
) -> str:
    """Return the Verilog storage declaration for a fixed-point signal."""
    sign = " signed" if signed else ""
    return f"logic{sign} [{width - 1}:0]"


def encode_float(
    emitter: VerilogConversionEmitter,
    value: float,
    width: int,
    frac_bits: int,
    signed: bool,
) -> str:
    """Encode a floating-point literal using the configured fixed-point format."""
    scaled = int(round(value * (2**frac_bits)))
    if signed:
        return f"{width}'sd{scaled}"
    masked = scaled % (1 << width)
    return f"{width}'d{masked}"


def literal_param_name(
    emitter: VerilogConversionEmitter,
    value: float,
    width: int,
    frac_bits: int,
    signed: bool,
    ctx: VerilogEmissionContext | None = None,
) -> str:
    """Return a stable parameter name for a fixed-point literal."""
    ctx = ctx or emitter._emission_context
    assert ctx is not None
    key = (value, width, frac_bits, signed)
    if key in ctx.literal_params:
        return ctx.literal_params[key]

    base = f"_VAL_{sanitize_literal_value(emitter, value)}"
    enc = ctx.config.real_encoding
    if enc is not None and (enc.width, enc.frac_bits, enc.signed) != (
        width,
        frac_bits,
        signed,
    ):
        base = f"{base}_{fixed_literal_encoding_suffix(emitter, width, frac_bits)}"
    name = base
    suffix = 2
    while name in ctx.literal_params.values():
        name = f"{base}_{suffix}"
        suffix += 1
    ctx.literal_params[key] = name
    return name


def fixed_literal_encoding_suffix(
    emitter: VerilogConversionEmitter, width: int, frac_bits: int
) -> str:
    """Return the suffix used for non-default fixed-point literal names."""
    return f"Q{width - frac_bits}_{frac_bits}"


def integer_literal_ref(
    emitter: VerilogConversionEmitter, value: float, width: int, signed: bool
) -> str:
    """Return a sized integer literal for a packed Verilog target."""
    integer_value = int(round(value))
    if signed:
        return f"{width}'sd{integer_value}"
    masked = integer_value % (1 << width)
    return f"{width}'d{masked}"


def sanitize_literal_value(emitter: VerilogConversionEmitter, value: float) -> str:
    """Convert a numeric literal into a Verilog-safe identifier fragment."""
    text = str(value)
    text = text.replace("-", "NEG_")
    text = text.replace(".", "_")
    return text


def fixed_literal_ref(
    emitter: VerilogConversionEmitter,
    value: float,
    width: int,
    frac_bits: int,
    signed: bool,
    ctx: VerilogEmissionContext | None = None,
) -> str:
    """Return a reference to a generated fixed-point literal parameter."""
    return literal_param_name(emitter, value, width, frac_bits, signed, ctx)


def emit_literal_params(
    emitter: VerilogConversionEmitter, ctx: VerilogEmissionContext | None = None
) -> str:
    """Emit the generated fixed-point literal parameter block."""
    ctx = ctx or emitter._emission_context
    assert ctx is not None
    if not ctx.literal_params:
        return ""

    lines: list[str] = []
    for (value, width, frac_bits, signed), name in sorted(
        ctx.literal_params.items(), key=lambda item: item[1]
    ):
        lines.append(
            f"// {name} = {value} in fixed-point Q{width - frac_bits}.{frac_bits}"
        )
        lines.append(
            f"localparam {fixed_storage_decl(emitter, width, signed)} {name} = {encode_float(emitter, value, width, frac_bits, signed)};"
        )
    lines.append("")
    return "\n".join(lines)


def emit_constant_in_encoding(
    emitter: VerilogConversionEmitter,
    value: float,
    target_encoding: VerilogEncoding,
    ctx: VerilogEmissionContext,
) -> str:
    """Emit one numeric literal in the requested Verilog encoding."""
    if target_encoding.kind == "fixed":
        return emitter._fixed_literal_ref(
            value,
            target_encoding.width,
            target_encoding.frac_bits,
            target_encoding.signed,
            ctx,
        )
    integer_value = int(round(value))
    if target_encoding.width == 1 and target_encoding.kind == "logic":
        return "1'b1" if integer_value != 0 else "1'b0"
    return emitter._integer_literal_ref(
        value, target_encoding.width, target_encoding.signed
    )


def emit_constant_expression(
    emitter: VerilogConversionEmitter, value: float, ctx: VerilogEmissionContext
) -> str:
    """Emit one fixed-point constant expression using the module encoding."""
    enc = ctx.config.real_encoding
    assert enc is not None
    return emitter._fixed_literal_ref(
        value,
        enc.width,
        enc.frac_bits,
        enc.signed,
        ctx,
    )
