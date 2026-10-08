"""Verilog conversion helper generation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .literals import (
    encode_float,
    emit_literal_params,
    fixed_literal_encoding_suffix,
    fixed_literal_ref,
    fixed_storage_decl,
    integer_literal_ref,
    literal_param_name,
    sanitize_literal_value,
)

if TYPE_CHECKING:
    from .context import VerilogEmissionContext


def conversion_helper_name(
    emitter: VerilogConversionEmitter,
    source_kind: str,
    source_width: int,
    source_signed: bool,
    source_frac_bits: int,
    target_kind: str,
    target_width: int,
    target_signed: bool,
    target_frac_bits: int,
    ctx: VerilogEmissionContext | None = None,
) -> str:
    """Return a stable helper name for a conversion between two encodings."""
    ctx = ctx or emitter._emission_context
    assert ctx is not None
    key = (
        source_kind,
        source_width,
        source_signed,
        source_frac_bits,
        target_kind,
        target_width,
        target_signed,
        target_frac_bits,
    )
    if key not in ctx.conversion_helpers:
        ctx.conversion_helpers[key] = (
            f"conv_{conversion_descriptor(emitter, source_kind, source_width, source_signed, source_frac_bits)}"
            f"_to_{conversion_descriptor(emitter, target_kind, target_width, target_signed, target_frac_bits)}"
        )
    return ctx.conversion_helpers[key]


def conversion_descriptor(
    emitter: VerilogConversionEmitter,
    kind: str,
    width: int,
    signed: bool,
    frac_bits: int,
) -> str:
    """Return a short descriptor used in generated helper names."""
    sign = "s" if signed else "u"
    if kind == "fixed":
        return f"{sign}fixed_{width}_{frac_bits}"
    if width == 1:
        return "logic"
    return f"logic_{width}"


def type_decl(
    emitter: VerilogConversionEmitter, kind: str, width: int, signed: bool
) -> str:
    """Return the Verilog type declaration for a signal kind."""
    if kind == "logic":
        if width == 1:
            return "logic"
        return f"logic [{width - 1}:0]"
    sign = " signed" if signed else ""
    if width == 1:
        return f"logic{sign}"
    return f"logic{sign} [{width - 1}:0]"


def emit_conversion_helpers(
    emitter: VerilogConversionEmitter, ctx: VerilogEmissionContext | None = None
) -> str:
    """Emit the conversion helper block used by generated Verilog modules."""
    ctx = ctx or emitter._emission_context
    assert ctx is not None
    if not ctx.conversion_helpers:
        return ""

    helper_lines: list[str] = []
    for key, name in sorted(ctx.conversion_helpers.items(), key=lambda item: item[1]):
        (
            source_kind,
            source_width,
            source_signed,
            source_frac_bits,
            target_kind,
            target_width,
            target_signed,
            target_frac_bits,
        ) = key
        helper_lines.extend(
            build_conversion_helper(
                emitter,
                name,
                source_kind,
                source_width,
                source_signed,
                source_frac_bits,
                target_kind,
                target_width,
                target_signed,
                target_frac_bits,
                ctx,
            )
        )
        helper_lines.append("")

    return "\n".join(helper_lines)


def build_conversion_helper(
    emitter: VerilogConversionEmitter,
    name: str,
    source_kind: str,
    source_width: int,
    source_signed: bool,
    source_frac_bits: int,
    target_kind: str,
    target_width: int,
    target_signed: bool,
    target_frac_bits: int,
    ctx: VerilogEmissionContext | None = None,
) -> list[str]:
    """Build one Verilog conversion helper function definition."""
    input_decl = type_decl(emitter, source_kind, source_width, source_signed)
    output_decl = type_decl(emitter, target_kind, target_width, target_signed)
    expr = conversion_expression(
        emitter,
        source_kind,
        source_width,
        source_signed,
        source_frac_bits,
        target_kind,
        target_width,
        target_signed,
        target_frac_bits,
        ctx,
    )
    return [
        f"function automatic {output_decl} {name}(",
        f"    input {input_decl} value",
        ");",
        f"    {name} = {expr};",
        "endfunction",
    ]


def conversion_expression(
    emitter: VerilogConversionEmitter,
    source_kind: str,
    source_width: int,
    source_signed: bool,
    source_frac_bits: int,
    target_kind: str,
    target_width: int,
    target_signed: bool,
    target_frac_bits: int,
    ctx: VerilogEmissionContext | None = None,
) -> str:
    """Return the expression used inside a conversion helper."""
    ctx = ctx or emitter._emission_context
    if target_kind == "fixed":
        if source_kind == "fixed":
            delta = target_frac_bits - source_frac_bits
            if delta > 0:
                return f"(value <<< {delta})"
            if delta < 0:
                return f"(value >>> {-delta})"
            return "value"
        if source_kind == "logic":
            if source_width > 1:
                if target_frac_bits > 0:
                    return f"(value <<< {target_frac_bits})"
                return "value"
            return f"(value ? {fixed_literal_ref(emitter, 1.0, target_width, target_frac_bits, target_signed, ctx)} : '0)"

    if target_kind == "logic":
        if source_kind == "logic":
            return "value"
        if source_kind == "fixed":
            if target_width == 1:
                return "(value != '0)"
            if source_frac_bits > 0:
                return f"(value >>> {source_frac_bits})"
            return "value"

    raise ValueError(
        f"Unsupported conversion from {source_kind}({source_width},{source_signed},{source_frac_bits}) "
        f"to {target_kind}({target_width},{target_signed},{target_frac_bits})"
    )


class VerilogConversionEmitter:
    """Emit Verilog conversion helpers and fixed-point literal parameters."""

    def _type_info_encoding(self, type_info):
        from .encodings import type_info_encoding

        return type_info_encoding(self, type_info)

    def _type_info_decl(self, type_info) -> str:
        from .encodings import type_info_decl

        return type_info_decl(self, type_info)

    def _fixed_storage_decl(self, width: int, signed: bool) -> str:
        return fixed_storage_decl(self, width, signed)

    def _encode_float(
        self, value: float, width: int, frac_bits: int, signed: bool
    ) -> str:
        return encode_float(self, value, width, frac_bits, signed)

    def _literal_param_name(
        self,
        value: float,
        width: int,
        frac_bits: int,
        signed: bool,
        ctx: VerilogEmissionContext | None = None,
    ) -> str:
        return literal_param_name(self, value, width, frac_bits, signed, ctx)

    def _fixed_literal_encoding_suffix(self, width: int, frac_bits: int) -> str:
        return fixed_literal_encoding_suffix(self, width, frac_bits)

    def _integer_literal_ref(self, value: float, width: int, signed: bool) -> str:
        return integer_literal_ref(self, value, width, signed)

    def _sanitize_literal_value(self, value: float) -> str:
        return sanitize_literal_value(self, value)

    def _fixed_literal_ref(
        self,
        value: float,
        width: int,
        frac_bits: int,
        signed: bool,
        ctx: VerilogEmissionContext | None = None,
    ) -> str:
        return fixed_literal_ref(self, value, width, frac_bits, signed, ctx)

    def _emit_literal_params(self, ctx: VerilogEmissionContext | None = None) -> str:
        return emit_literal_params(self, ctx)

    def _conversion_helper_name(
        self,
        source_kind: str,
        source_width: int,
        source_signed: bool,
        source_frac_bits: int,
        target_kind: str,
        target_width: int,
        target_signed: bool,
        target_frac_bits: int,
        ctx: VerilogEmissionContext | None = None,
    ) -> str:
        return conversion_helper_name(
            self,
            source_kind,
            source_width,
            source_signed,
            source_frac_bits,
            target_kind,
            target_width,
            target_signed,
            target_frac_bits,
            ctx,
        )

    def _conversion_descriptor(
        self, kind: str, width: int, signed: bool, frac_bits: int
    ) -> str:
        return conversion_descriptor(self, kind, width, signed, frac_bits)

    def _type_decl(self, kind: str, width: int, signed: bool) -> str:
        return type_decl(self, kind, width, signed)

    def _emit_conversion_helpers(
        self, ctx: VerilogEmissionContext | None = None
    ) -> str:
        return emit_conversion_helpers(self, ctx)

    def _build_conversion_helper(
        self,
        name: str,
        source_kind: str,
        source_width: int,
        source_signed: bool,
        source_frac_bits: int,
        target_kind: str,
        target_width: int,
        target_signed: bool,
        target_frac_bits: int,
        ctx: VerilogEmissionContext | None = None,
    ) -> list[str]:
        return build_conversion_helper(
            self,
            name,
            source_kind,
            source_width,
            source_signed,
            source_frac_bits,
            target_kind,
            target_width,
            target_signed,
            target_frac_bits,
            ctx,
        )

    def _conversion_expression(
        self,
        source_kind: str,
        source_width: int,
        source_signed: bool,
        source_frac_bits: int,
        target_kind: str,
        target_width: int,
        target_signed: bool,
        target_frac_bits: int,
        ctx: VerilogEmissionContext | None = None,
    ) -> str:
        return conversion_expression(
            self,
            source_kind,
            source_width,
            source_signed,
            source_frac_bits,
            target_kind,
            target_width,
            target_signed,
            target_frac_bits,
            ctx,
        )
