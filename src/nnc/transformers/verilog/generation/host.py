"""Type-only interface shared by the Verilog emitter mixins.

``VerilogTransformer`` is assembled from mixins (structure, state, references,
conversions, expressions) that call each other's methods through ``self``.
This class declares those cross-mixin members once, so a type checker can
check the calls; each mixin subclasses it only while type checking (see
``_Host`` in the mixin modules) and overrides the members it implements, which
also checks that the declarations and the implementations agree. Nothing here
exists at runtime.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ....model.system import NncSystem
from ...base_transformer import BaseTransformer
from ..hardware_config import (
    PortConfig,
    VerilogEncoding,
    VerilogHardwareConfig,
    VerilogTypeInfo,
)

if TYPE_CHECKING:
    from .context import VerilogEmissionContext


class VerilogEmitterHost(BaseTransformer):
    """Members the Verilog emitter mixins use from one another."""

    _emission_context: VerilogEmissionContext | None

    def _config_for(self, system: NncSystem) -> VerilogHardwareConfig:
        raise NotImplementedError

    def _infer_ports(self, system: NncSystem) -> list[PortConfig]:
        raise NotImplementedError

    def _state_name(self, variable_name: str) -> str:
        raise NotImplementedError

    def _type_decl(self, kind: str, width: int, signed: bool) -> str:
        raise NotImplementedError

    def _type_info_encoding(self, type_info: VerilogTypeInfo) -> VerilogEncoding:
        raise NotImplementedError

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
        raise NotImplementedError

    def visit(self, node: Any, ctx: VerilogEmissionContext | None = None) -> str:
        raise NotImplementedError

    def _variable_signal_name(
        self, variable_name: str, ctx: VerilogEmissionContext
    ) -> str:
        raise NotImplementedError

    def _emit_constant_in_encoding(
        self,
        value: float,
        target_encoding: VerilogEncoding,
        ctx: VerilogEmissionContext,
    ) -> str:
        raise NotImplementedError

    def _emit_in_encoding(
        self,
        node: Any,
        target_encoding: VerilogEncoding,
        ctx: VerilogEmissionContext,
    ) -> str:
        raise NotImplementedError

    def _encoding_from_parts(
        self, kind: str, width: int, signed: bool, frac_bits: int
    ) -> VerilogEncoding:
        raise NotImplementedError

    def _variable_expression_encoding(
        self, variable_name: str, ctx: VerilogEmissionContext | None = None
    ) -> VerilogEncoding:
        raise NotImplementedError

    def _variable_state_encoding(
        self, variable_name: str, ctx: VerilogEmissionContext | None = None
    ) -> VerilogEncoding:
        raise NotImplementedError

    def _integer_literal_ref(self, value: float, width: int, signed: bool) -> str:
        raise NotImplementedError

    def _fixed_literal_ref(
        self,
        value: float,
        width: int,
        frac_bits: int,
        signed: bool,
        ctx: VerilogEmissionContext | None = None,
    ) -> str:
        raise NotImplementedError

    def _reference_signal_name(self, reference: str) -> str:
        raise NotImplementedError

    def _reference_signal(self, reference: str) -> str:
        raise NotImplementedError

    def _reference_encoding(
        self, reference: str, ctx: VerilogEmissionContext | None = None
    ) -> VerilogEncoding:
        raise NotImplementedError

    def _resolve_connection(
        self,
        reference: str,
        target_kind: str,
        target_width: int,
        target_signed: bool,
        target_frac_bits: int,
        ctx: VerilogEmissionContext | None = None,
    ) -> str:
        raise NotImplementedError

    def _convert_signal_by_encoding(
        self,
        signal: str,
        source_encoding: VerilogEncoding,
        target_encoding: VerilogEncoding,
        ctx: VerilogEmissionContext | None = None,
    ) -> str:
        raise NotImplementedError

    def _maybe_convert_signal(
        self,
        reference: str,
        signal: str,
        target_encoding: VerilogEncoding,
        ctx: VerilogEmissionContext | None = None,
    ) -> str:
        raise NotImplementedError

    def _top_port_config(
        self, port_name: str, ctx: VerilogEmissionContext | None = None
    ) -> PortConfig | None:
        raise NotImplementedError

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
        raise NotImplementedError
