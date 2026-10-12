"""Type-only interface shared by the Python emitter mixins.

``PythonTransformer`` is assembled from mixins (core, CSV script, expression)
that call each other's methods through ``self``. This class declares those
cross-mixin members once so a type checker can check the calls; each mixin
subclasses it only while type checking (see ``_Host`` in the mixin modules) and
overrides the members it implements, which also checks that the declarations
and the implementations agree. Nothing here exists at runtime.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...model.system import NncSystem
from ..base_transformer import BaseTransformer

if TYPE_CHECKING:
    from .emission_context import PythonEmissionContext


class PythonEmitterHost(BaseTransformer):
    """Members the Python emitter mixins use from one another."""

    _emission_context: PythonEmissionContext | None
    _current_system: NncSystem | None
    _uses_random: bool

    def _class_name(
        self, system: NncSystem, ctx: PythonEmissionContext | None = None
    ) -> str:
        raise NotImplementedError

    def _get_producer_variables(self, producer_expr: Any) -> set[str]:
        raise NotImplementedError

    def _reference_code(self, reference: str) -> str:
        raise NotImplementedError

    def _input_vars(self, system: NncSystem) -> list[str]:
        raise NotImplementedError

    def _output_vars(self, system: NncSystem) -> list[str]:
        raise NotImplementedError

    def visit(self, node: Any) -> str:
        raise NotImplementedError

    def visit_value(self, value: Any) -> str:
        raise NotImplementedError
