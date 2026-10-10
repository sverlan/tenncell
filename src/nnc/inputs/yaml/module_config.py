"""Shared YAML-facing module configuration for TENNCell systems."""

from __future__ import annotations

import math

from dataclasses import dataclass, field

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from ...model.system import NncSystem


def normalize_connection(value: object) -> str | None:
    """Return a YAML connection value as stored in ``connections``.

    Args:
        value: The YAML value: a reference, a number, or ``None``.

    Returns:
        The reference text, a number written as its decimal text (``5``,
        ``2.5``), or ``None`` for a connection left empty (the input gets 0).

    Raises:
        ValueError: For a boolean, a non-finite number, or another type.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("must be a reference or a number, not a boolean")
    if isinstance(value, int):
        try:
            float(value)
        except OverflowError:
            raise ValueError("is a number too large for a connection") from None
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"must be a finite number, not {value}")
        return repr(value)
    if isinstance(value, str):
        return value.strip()
    raise ValueError(f"must be a reference or a number, not {type(value).__name__}")


def connection_number(reference: str) -> float | None:
    """Return the value of a connection that is a number, else ``None``.

    Numbers are recognized before references, so ``2.5`` is a value and not
    ``alias.port``.
    """
    try:
        value = float(reference)
    except (TypeError, ValueError, OverflowError):
        return None
    return value if math.isfinite(value) else None


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
