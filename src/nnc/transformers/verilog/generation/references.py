"""Verilog reference and connection resolution helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..hardware_config import (
    PortConfig,
    VerilogEncoding,
    VerilogFixedPointEncoding,
    VerilogLogicEncoding,
)
from .encodings import encoding_from_parts

if TYPE_CHECKING:
    from .context import VerilogEmissionContext


def variable_expression_encoding(
    emitter: VerilogReferenceResolver,
    variable_name: str,
    ctx: VerilogEmissionContext | None = None,
) -> VerilogEncoding:
    """Return the expression encoding used for one variable reference."""
    ctx = ctx or emitter._emission_context
    assert ctx is not None
    if variable_name in ctx.resolved_var_types:
        return emitter._type_info_encoding(ctx.resolved_var_types[variable_name])
    if (
        variable_name in ctx.top_ports
        or variable_name in ctx.external_output_bindings
        or variable_name in ctx.import_output_bindings
    ):
        return reference_encoding(emitter, variable_name, ctx)
    enc = ctx.config.real_encoding
    assert enc is not None
    return enc.to_verilog_encoding()


def variable_state_encoding(
    emitter: VerilogReferenceResolver,
    variable_name: str,
    ctx: VerilogEmissionContext | None = None,
) -> VerilogEncoding:
    """Return the storage encoding used for one local variable."""
    ctx = ctx or emitter._emission_context
    assert ctx is not None
    if variable_name in ctx.resolved_var_types:
        return emitter._type_info_encoding(ctx.resolved_var_types[variable_name])
    if (
        variable_name in ctx.top_ports
        or variable_name in ctx.external_output_bindings
        or variable_name in ctx.import_output_bindings
    ):
        return reference_encoding(emitter, variable_name, ctx)
    enc = ctx.config.real_encoding
    assert enc is not None
    return enc.to_verilog_encoding()


def reference_signal_name(emitter: VerilogReferenceResolver, reference: str) -> str:
    """Convert a dotted TENNCell reference into a Verilog signal name."""
    return reference.replace(".", "__")


def resolve_connection(
    emitter: VerilogReferenceResolver,
    reference: str,
    target_kind: str,
    target_width: int,
    target_signed: bool,
    target_frac_bits: int,
    ctx: VerilogEmissionContext | None = None,
) -> str:
    """Resolve a connection reference into a Verilog signal or helper call."""
    ctx = ctx or emitter._emission_context
    target_encoding = encoding_from_parts(
        emitter, target_kind, target_width, target_signed, target_frac_bits
    )
    if reference == "0":
        return "0"
    if "." in reference:
        signal = reference_signal(emitter, reference)
        return maybe_convert_signal(emitter, reference, signal, target_encoding, ctx)
    top_port = top_port_config(emitter, reference, ctx)
    if top_port is not None:
        return maybe_convert_signal(
            emitter,
            reference,
            top_port_signal_name(emitter, reference, ctx),
            target_encoding,
            ctx,
        )
    if ctx is not None and reference in ctx.local_variables:
        signal = emitter._state_name(reference)
        source_encoding = reference_encoding(emitter, reference, ctx)
        if source_encoding == target_encoding:
            return signal
        helper_name = emitter._conversion_helper_name(
            source_encoding.kind,
            source_encoding.width,
            source_encoding.signed,
            source_encoding.frac_bits if source_encoding.kind == "fixed" else 0,
            target_encoding.kind,
            target_encoding.width,
            target_encoding.signed,
            target_encoding.frac_bits if target_encoding.kind == "fixed" else 0,
            ctx,
        )
        return f"{helper_name}({signal})"
    if ctx is not None and reference in ctx.import_output_bindings:
        signal = reference_signal(emitter, reference)
        return maybe_convert_signal(emitter, reference, signal, target_encoding, ctx)
    return reference


def convert_signal_by_encoding(
    emitter: VerilogReferenceResolver,
    signal: str,
    source_encoding: VerilogEncoding,
    target_encoding: VerilogEncoding,
    ctx: VerilogEmissionContext | None = None,
) -> str:
    """Convert one signal between two explicit encodings."""
    ctx = ctx or emitter._emission_context
    if (
        source_encoding.kind == target_encoding.kind
        and source_encoding.width == target_encoding.width
        and source_encoding.signed == target_encoding.signed
        and (
            source_encoding.kind != "fixed"
            or source_encoding.frac_bits == target_encoding.frac_bits
        )
    ):
        return signal
    if (
        source_encoding.kind == "fixed"
        and target_encoding.kind == "fixed"
        and source_encoding.signed != target_encoding.signed
    ):
        raise ValueError("Signedness mismatch for fixed-point conversion")
    helper_name = emitter._conversion_helper_name(
        source_encoding.kind,
        source_encoding.width,
        source_encoding.signed,
        source_encoding.frac_bits if source_encoding.kind == "fixed" else 0,
        target_encoding.kind,
        target_encoding.width,
        target_encoding.signed,
        target_encoding.frac_bits if target_encoding.kind == "fixed" else 0,
        ctx,
    )
    return f"{helper_name}({signal})"


def reference_signal(emitter: VerilogReferenceResolver, reference: str) -> str:
    """Resolve a reference to the signal name used in generated Verilog."""
    return reference_signal_name(emitter, reference)


def top_port_config(
    emitter: VerilogReferenceResolver,
    port_name: str,
    ctx: VerilogEmissionContext | None = None,
) -> PortConfig | None:
    """Look up the configured top-level port for a signal name."""
    ctx = ctx or emitter._emission_context
    assert ctx is not None
    return ctx.top_ports.get(port_name)


def top_port_signal_name(
    emitter: VerilogReferenceResolver,
    port_name: str,
    ctx: VerilogEmissionContext | None = None,
) -> str:
    """Return the emitted Verilog name for a top-level port binding."""
    port = top_port_config(emitter, port_name, ctx)
    assert port is not None
    return port.verilog_name


def convert_local_fixed_to_target(
    emitter: VerilogReferenceResolver,
    signal_name: str,
    target_kind: str,
    target_width: int,
    target_signed: bool,
    ctx: VerilogEmissionContext | None = None,
) -> str:
    """Convert a local fixed-point signal to the target boundary type."""
    ctx = ctx or emitter._emission_context
    assert ctx is not None
    signal = emitter._state_name(signal_name)
    enc = ctx.config.real_encoding
    assert enc is not None
    if (
        target_kind == "fixed"
        and target_width == enc.width
        and target_signed == enc.signed
    ):
        return signal
    helper_name = emitter._conversion_helper_name(
        "fixed",
        enc.width,
        enc.signed,
        enc.frac_bits,
        target_kind,
        target_width,
        target_signed,
        0,
        ctx,
    )
    return f"{helper_name}({signal})"


def external_output_to_target(
    emitter: VerilogReferenceResolver,
    signal: str,
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
    """Convert an external module output to the target boundary type."""
    source_encoding = encoding_from_parts(
        emitter, source_kind, source_width, source_signed, source_frac_bits
    )
    target_encoding = encoding_from_parts(
        emitter, target_kind, target_width, target_signed, target_frac_bits
    )
    if (
        source_encoding.kind == target_encoding.kind
        and source_encoding.width == target_encoding.width
        and source_encoding.signed == target_encoding.signed
        and (
            source_encoding.kind != "fixed"
            or source_encoding.frac_bits == target_encoding.frac_bits
        )
    ):
        return signal
    helper_name = emitter._conversion_helper_name(
        source_encoding.kind,
        source_encoding.width,
        source_encoding.signed,
        source_encoding.frac_bits if source_encoding.kind == "fixed" else 0,
        target_encoding.kind,
        target_encoding.width,
        target_encoding.signed,
        target_encoding.frac_bits if target_encoding.kind == "fixed" else 0,
        ctx,
    )
    return f"{helper_name}({signal})"


def reference_encoding(
    emitter: VerilogReferenceResolver,
    reference: str,
    ctx: VerilogEmissionContext | None = None,
) -> VerilogEncoding:
    """Return the encoding object for a TENNCell or boundary reference."""
    ctx = ctx or emitter._emission_context
    assert ctx is not None
    config = ctx.config
    if reference in {config.clock.name, config.reset.name}:
        return VerilogLogicEncoding(kind="logic", width=1, signed=False)
    if reference in ctx.resolved_var_types:
        return emitter._type_info_encoding(ctx.resolved_var_types[reference])
    if reference in ctx.top_ports:
        port = ctx.top_ports[reference]
        enc = config.real_encoding
        assert enc is not None
        if port.kind == "fixed":
            return VerilogFixedPointEncoding(
                kind="fixed",
                width=port.width,
                signed=port.signed,
                frac_bits=enc.frac_bits,
            )
        return VerilogLogicEncoding(kind="logic", width=port.width, signed=port.signed)

    if reference in ctx.external_output_bindings:
        _, port = ctx.external_output_bindings[reference]
        enc = config.real_encoding
        assert enc is not None
        if port.kind == "fixed":
            return VerilogFixedPointEncoding(
                kind="fixed",
                width=port.width,
                signed=port.signed,
                frac_bits=enc.frac_bits,
            )
        return VerilogLogicEncoding(kind="logic", width=port.width, signed=port.signed)

    if reference in ctx.import_output_bindings:
        _, port = ctx.import_output_bindings[reference]
        imported_name = reference
        for item in ctx.system.imports:
            if imported_name in item.system.output_variables:
                imported_config = emitter._config_for(item.system)
                imported_ports = {
                    p.name: p
                    for p in (
                        imported_config.ports or emitter._infer_ports(item.system)
                    )
                }
                imported_port = imported_ports.get(imported_name, port)
                if imported_port.kind == "fixed":
                    assert imported_config.real_encoding is not None
                    return VerilogFixedPointEncoding(
                        kind="fixed",
                        width=imported_port.width,
                        signed=imported_port.signed,
                        frac_bits=imported_config.real_encoding.frac_bits,
                    )
                return VerilogLogicEncoding(
                    kind="logic",
                    width=imported_port.width,
                    signed=imported_port.signed,
                )
        if port.kind == "fixed":
            return VerilogFixedPointEncoding(
                kind="fixed",
                width=port.width,
                signed=port.signed,
                frac_bits=config.real_encoding.frac_bits,
            )
        return VerilogLogicEncoding(kind="logic", width=port.width, signed=port.signed)

    if reference in ctx.local_variables:
        enc = config.real_encoding
        assert enc is not None
        return enc.to_verilog_encoding()

    constant_name = reference.replace(".", "__")
    if constant_name in ctx.system.constants:
        enc = config.real_encoding
        assert enc is not None
        return enc.to_verilog_encoding()
    head, _, tail = reference.partition(".")
    for item in ctx.system.imports:
        if item.alias == head:
            imported = item.system
            if tail in imported.output_variables:
                enc = emitter._config_for(imported).real_encoding
                assert enc is not None
                return enc.to_verilog_encoding()
            if tail in imported.input_variables:
                enc = emitter._config_for(imported).real_encoding
                assert enc is not None
                return enc.to_verilog_encoding()

    raise ValueError(f"Unknown connection reference '{reference}'")


def maybe_convert_signal(
    emitter: VerilogReferenceResolver,
    reference: str,
    signal: str,
    target_encoding: VerilogEncoding,
    ctx: VerilogEmissionContext | None = None,
) -> str:
    """Apply a conversion helper only when the source and target differ."""
    ctx = ctx or emitter._emission_context
    source_encoding = reference_encoding(emitter, reference, ctx)
    if (
        source_encoding.kind == target_encoding.kind
        and source_encoding.width == target_encoding.width
        and source_encoding.signed == target_encoding.signed
        and (
            source_encoding.kind != "fixed"
            or source_encoding.frac_bits == target_encoding.frac_bits
        )
    ):
        return signal
    if (
        source_encoding.kind == "fixed"
        and target_encoding.kind == "fixed"
        and source_encoding.signed != target_encoding.signed
    ):
        raise ValueError(f"Signedness mismatch for reference '{reference}'")
    helper_name = emitter._conversion_helper_name(
        source_encoding.kind,
        source_encoding.width,
        source_encoding.signed,
        source_encoding.frac_bits if source_encoding.kind == "fixed" else 0,
        target_encoding.kind,
        target_encoding.width,
        target_encoding.signed,
        target_encoding.frac_bits if target_encoding.kind == "fixed" else 0,
        ctx,
    )
    return f"{helper_name}({signal})"


class VerilogReferenceResolver:
    """Resolve TENNCell references and boundary conversions for Verilog emission."""

    def _encoding_from_parts(self, kind, width, signed, frac_bits):
        return encoding_from_parts(self, kind, width, signed, frac_bits)

    def _variable_expression_encoding(
        self, variable_name: str, ctx: VerilogEmissionContext | None = None
    ):
        return variable_expression_encoding(self, variable_name, ctx)

    def _variable_state_encoding(
        self, variable_name: str, ctx: VerilogEmissionContext | None = None
    ):
        return variable_state_encoding(self, variable_name, ctx)

    def _reference_signal_name(self, reference: str) -> str:
        return reference_signal_name(self, reference)

    def _resolve_connection(
        self,
        reference: str,
        target_kind: str,
        target_width: int,
        target_signed: bool,
        target_frac_bits: int,
        ctx: VerilogEmissionContext | None = None,
    ) -> str:
        return resolve_connection(
            self,
            reference,
            target_kind,
            target_width,
            target_signed,
            target_frac_bits,
            ctx,
        )

    def _convert_signal_by_encoding(
        self,
        signal: str,
        source_encoding,
        target_encoding,
        ctx: VerilogEmissionContext | None = None,
    ) -> str:
        return convert_signal_by_encoding(
            self, signal, source_encoding, target_encoding, ctx
        )

    def _reference_signal(self, reference: str) -> str:
        return reference_signal(self, reference)

    def _top_port_config(
        self, port_name: str, ctx: VerilogEmissionContext | None = None
    ):
        return top_port_config(self, port_name, ctx)

    def _top_port_signal_name(
        self, port_name: str, ctx: VerilogEmissionContext | None = None
    ) -> str:
        return top_port_signal_name(self, port_name, ctx)

    def _convert_local_fixed_to_target(
        self,
        signal_name: str,
        target_kind: str,
        target_width: int,
        target_signed: bool,
        ctx: VerilogEmissionContext | None = None,
    ) -> str:
        return convert_local_fixed_to_target(
            self, signal_name, target_kind, target_width, target_signed, ctx
        )

    def _external_output_to_target(
        self,
        signal: str,
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
        return external_output_to_target(
            self,
            signal,
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

    def _reference_encoding(
        self, reference: str, ctx: VerilogEmissionContext | None = None
    ):
        return reference_encoding(self, reference, ctx)

    def _maybe_convert_signal(
        self,
        reference: str,
        signal: str,
        target_encoding,
        ctx: VerilogEmissionContext | None = None,
    ) -> str:
        return maybe_convert_signal(self, reference, signal, target_encoding, ctx)
