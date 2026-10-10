"""Render generic-property conditions as SystemVerilog checker expressions.

The Verilog emitter itself renders the conditions, so a checker computes them
with the encodings, literals and conversion helpers of the generated RTL. Only
the names change: every TENNCell value is read from the checker signal that
carries it (root inputs from their row-aligned copies).
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from ..model.system import NncSystem
from ..parser.ast import BooleanExpression
from .verilog.generation.context import VerilogEmissionContext
from .verilog.generation.encodings import VerilogEncoding
from .verilog.generation.observation import VerilogObservation
from .verilog.hardware_config import VerilogHardwareConfig
from .verilog_transformer import VerilogTransformer


class SvaConditionRenderer(VerilogTransformer):
    """Render conditions of one root module for its SVA checker.

    Literal parameters and conversion helpers used by the rendered conditions
    are collected and returned by ``declarations``.
    """

    def __init__(
        self,
        verilog_configs: dict[Path, VerilogHardwareConfig],
        system: NncSystem,
        observation: VerilogObservation,
    ) -> None:
        super().__init__(verilog_configs)
        self._observation = observation
        self._names: Mapping[str, str] | None = None
        self._ctx: VerilogEmissionContext = self._build_emission_context(system)

    def render(self, condition: BooleanExpression, names: Mapping[str, str]) -> str:
        """Return the checker expression of a condition.

        Args:
            condition: Bound condition of a generic property.
            names: Checker signal for every TENNCell name the condition reads.

        Returns:
            A one-bit SystemVerilog expression.
        """
        self._names = names
        try:
            return self.visit(condition, self._ctx)
        finally:
            self._names = None

    def declarations(self) -> str:
        """Return the literal parameters and conversion helpers used so far.

        Returns:
            Declarations for the checker module scope, or ``""``.
        """
        # Helpers first: building one can add a literal parameter it reads.
        helpers = self._emit_conversion_helpers(self._ctx)
        literals = self._emit_literal_params(self._ctx)
        return "\n".join(part for part in (literals, helpers) if part)

    def declared_names(self) -> set[str]:
        """Return the names ``declarations`` declares (parameters, helpers).

        Returns:
            Identifiers of the literal parameters and conversion helpers.
        """
        return set(self._ctx.literal_params.values()) | set(
            self._ctx.conversion_helpers.values()
        )

    # Names and encodings of the checker ------------------------------------

    def _variable_signal_name(self, variable_name, ctx):
        if self._names is None:
            return super()._variable_signal_name(variable_name, ctx)
        return self._names[variable_name]

    def _reference_signal(self, reference: str) -> str:
        if self._names is None:
            return super()._reference_signal(reference)
        if reference in self._names:
            return self._names[reference]
        constant = reference.replace(".", "__")  # FSM state such as ctrl.DONE
        value = float(self._ctx.system.constants[constant].value)
        enc = self._ctx.config.real_encoding  # as the RTL encodes its constants
        assert enc is not None
        return self._encode_float(value, enc.width, enc.frac_bits, enc.signed)

    def _reference_encoding(self, reference, ctx=None) -> VerilogEncoding:
        signal = self._observation.signals.get(reference)
        if self._names is not None and signal is not None:
            # An imported port is read as its boundary wire is declared.
            return signal.encoding()
        return super()._reference_encoding(reference, ctx)
