"""Typed view of the TENNCell values observable in a generated RTL module.

Built from the same emission context and helpers as the RTL itself, so a
checker (SVA) that reads these signals sees exactly what the module computes.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal

from .conversions import port_declared_signed, storage_declared_signed
from .encodings import VerilogEncoding, encoding_from_parts
from .references import boundary_wire_name

if TYPE_CHECKING:
    from .context import VerilogEmissionContext

ObservedSignalKind = Literal[
    "state", "input_port", "binding_wire", "import_wire", "import_input"
]
EncodingKind = Literal["fixed", "logic"]

# Kinds of observed signals.
STATE: ObservedSignalKind = "state"  # `state_<var>` register of a local variable
INPUT_PORT: ObservedSignalKind = "input_port"  # root input port (under its `rename`)
# local wire driven by an imported or external output
BINDING_WIRE: ObservedSignalKind = "binding_wire"
# `<alias>__<port>` wire of an imported output
IMPORT_WIRE: ObservedSignalKind = "import_wire"
# value the parent drives into an imported input
IMPORT_INPUT: ObservedSignalKind = "import_input"

_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_$]*")


@dataclass(frozen=True, slots=True)
class ObservedSignal:
    """One TENNCell value as it appears in the generated module.

    Args:
        name: TENNCell name: a root variable (``x``) or an imported port
            (``alias.port``).
        expression: SystemVerilog expression for the value in the module scope.
        kind: One of ``STATE``, ``INPUT_PORT``, ``BINDING_WIRE``,
            ``IMPORT_WIRE``, ``IMPORT_INPUT``.
        encoding_kind: ``fixed`` (fixed point) or ``logic``.
        width: Bit width.
        signed: Whether the signal is declared signed in the generated module.
        frac_bits: Fractional bits (``0`` for ``logic``).
        connectable: Whether ``expression`` is a signal declared in the module,
            usable as a port connection (not a constant or conversion call).
        initial_value: Initial TENNCell value when row-aligned sampling needs a
            copy (root and imported inputs); otherwise ``None``.
    """

    name: str
    expression: str
    kind: ObservedSignalKind
    encoding_kind: EncodingKind
    width: int
    signed: bool
    frac_bits: int
    connectable: bool
    initial_value: float | None = None

    def encoding(self) -> VerilogEncoding:
        """Return a fresh encoding object for this signal.

        Returns:
            A new ``VerilogFixedPointEncoding`` or ``VerilogLogicEncoding`` with
            this signal's kind, width, signedness and fractional bits; changing
            it does not affect the signal.
        """
        return encoding_from_parts(
            None, self.encoding_kind, self.width, self.signed, self.frac_bits
        )


@dataclass(frozen=True, slots=True)
class VerilogObservation:
    """Observable interface of one generated RTL module.

    Args:
        module_name: Name of the generated module.
        clock: Clock signal name.
        reset: Reset signal name.
        reset_active_high: Whether the reset is active high.
        signals: Observed signals keyed by TENNCell name (read-only).
    """

    module_name: str
    clock: str
    reset: str
    reset_active_high: bool
    signals: Mapping[str, ObservedSignal]

    def signal(self, name: str) -> ObservedSignal:
        """Return the observed signal for a TENNCell name.

        Args:
            name: A root variable (``x``) or an imported port (``alias.port``).

        Returns:
            The signal as it appears in the generated module.

        Raises:
            KeyError: If the name is not observable in this module.
        """
        try:
            return self.signals[name]
        except KeyError:
            raise KeyError(
                f"'{name}' is not observable in module '{self.module_name}'"
            ) from None


def build_observation(emitter, ctx: VerilogEmissionContext) -> VerilogObservation:
    """Build the observation of the module described by ``ctx``.

    ``emitter`` is the ``VerilogTransformer`` that owns ``ctx``; its helpers
    decide every name and encoding, exactly as for the RTL.
    """
    system = ctx.system
    signals: dict[str, ObservedSignal] = {}

    for name in system.variables:
        if name in system.input_variables:
            kind = INPUT_PORT if name in ctx.top_ports else BINDING_WIRE
        elif name in ctx.local_variables:
            kind = STATE
        else:
            kind = BINDING_WIRE
        encoding = (
            emitter._variable_state_encoding(name, ctx)
            if kind == STATE
            else emitter._variable_expression_encoding(name, ctx)
        )
        signals[name] = _signal(
            name,
            emitter._variable_signal_name(name, ctx),
            kind,
            encoding,
            initial_value=(
                float(system.variables[name].value.value)
                if name in system.input_variables
                else None
            ),
        )

    for item in system.imports:
        imported_ports = emitter._port_map_for(item.system)
        frac_bits = emitter._config_for(item.system).real_encoding.frac_bits
        for output_name in item.system.output_variables:
            port = imported_ports.get(output_name)
            if port is None:
                continue
            signals[f"{item.alias}.{output_name}"] = _signal(
                f"{item.alias}.{output_name}",
                boundary_wire_name(item.alias, output_name),
                IMPORT_WIRE,
                _port_encoding(port, frac_bits),
            )

    # Imported inputs last: their connection may name any signal above.
    by_expression = {signal.expression: signal for signal in signals.values()}
    for item in system.imports:
        imported = item.system
        imported_ports = emitter._port_map_for(imported)
        frac_bits = emitter._config_for(imported).real_encoding.frac_bits
        for input_name in imported.input_variables:
            port = imported_ports.get(input_name)
            if port is None:
                continue
            encoding = _port_encoding(port, frac_bits)
            expression = emitter._resolve_connection(
                item.connections.get(input_name, "0"),
                encoding.kind,
                encoding.width,
                encoding.signed,
                frac_bits if encoding.kind == "fixed" else 0,
                ctx,
            )
            signal = _signal(
                f"{item.alias}.{input_name}",
                expression,
                IMPORT_INPUT,
                encoding,
                initial_value=float(imported.input_variables[input_name].value.value),
            )
            # A plain signal name is read through that signal's own declaration.
            declared = by_expression.get(expression)
            if declared is not None:
                signal = replace(signal, width=declared.width, signed=declared.signed)
            signals[signal.name] = signal

    return VerilogObservation(
        module_name=system.module_config.name,
        clock=ctx.config.clock.name,
        reset=ctx.config.reset.name,
        reset_active_high=ctx.config.reset.active_high,
        signals=MappingProxyType(signals),
    )


def _port_encoding(port, frac_bits: int) -> VerilogEncoding:
    return encoding_from_parts(
        None,
        port.kind,
        port.width,
        port.signed,
        frac_bits if port.kind == "fixed" else 0,
    )


def _signal(
    name: str,
    expression: str,
    kind: ObservedSignalKind,
    encoding: VerilogEncoding,
    initial_value: float | None = None,
) -> ObservedSignal:
    # Signedness as the RTL declares it, so a checker reads values exactly as
    # the module does (the same helpers produce the declarations).
    if kind == STATE:
        signed = storage_declared_signed(encoding.kind, encoding.width, encoding.signed)
    else:
        signed = port_declared_signed(encoding.width, encoding.signed)
    return ObservedSignal(
        name=name,
        expression=expression,
        kind=kind,
        encoding_kind=encoding.kind,
        width=encoding.width,
        signed=signed,
        frac_bits=encoding.frac_bits if encoding.kind == "fixed" else 0,
        connectable=_IDENTIFIER.fullmatch(expression) is not None,
        initial_value=initial_value,
    )
