"""Shared YAML-facing module configuration for TENNCell systems."""

from __future__ import annotations

from dataclasses import dataclass, field

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from ...model.system import NncSystem


@dataclass(slots=True)
class ImportConfig:
    """Imported TENNCell module wiring.

    Args:
        module: Absolute module path for the imported YAML file, as resolved by
            the YAML loader.
        alias: Import alias used to reference the child system.
        connections: Mapping of child input names to TENNCell reference strings or
            literal values.
        system: Loaded child system, or ``None`` while the import is still
            unresolved.

    Validation assumptions:
        The loader resolves ``module`` to an absolute file path and populates
        ``system`` before the model is used for simulation or transformation.
        ``alias`` must be unique within one parent system.
    """

    module: str
    alias: str
    connections: dict[str, str] = field(default_factory=dict)
    system: NncSystem | None = None


@dataclass(slots=True)
class ModuleConfig:
    """Shared TENNCell module metadata.

    Args:
        name: Module name. When YAML omits ``module.name``, the loader falls
            back to the source file stem.
        zero_reset_mode: Whether the runtime clears non-input variables at the
            start of each step.
        description: Optional human-readable description. The loader stores it
            as metadata but the runtime and transformers ignore it.

    Validation assumptions:
        ``name`` is always a non-empty string by the time the model is used.
        ``description`` is informational only and must not affect semantics.
    """

    name: str
    zero_reset_mode: bool = False
    description: str | None = None
