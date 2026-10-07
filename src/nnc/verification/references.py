"""Resolve verification placeholder names against a TENNCell system."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..parser.ast.expression import ReferenceExpression, VariableExpression

if TYPE_CHECKING:
    from ..model.system import NncSystem

VARIABLE = "variable"
CONSTANT = "constant"
IMPORTED = "imported"


@dataclass(frozen=True, slots=True)
class ResolvedReference:
    """A placeholder name resolved to one model entity.

    Args:
        name: Name as written in the placeholder.
        kind: ``variable``, ``constant``, or ``imported``.
        target: Local variable name, constant name (FSM states in lowered
            ``fsm__STATE`` form), or imported ``alias.port`` reference.
        value: Constant value for ``constant`` references, else ``None``.
        alias: Alias name when the placeholder named an alias, else ``None``.
    """

    name: str
    kind: str
    target: str
    value: float | None = None
    alias: str | None = None


def resolve_reference(name: str, system: "NncSystem") -> ResolvedReference:
    """Resolve a placeholder name to exactly one model entity.

    Candidates are local variables, constants, FSM states (``fsm.STATE``),
    aliases (resolved to their variable or imported target), and imported
    inputs/outputs (``alias.port``). All candidates are collected; there is no
    priority between them.

    Args:
        name: Placeholder name.
        system: TENNCell system the name must belong to.

    Returns:
        The single matching reference.

    Raises:
        ValueError: If the name matches nothing or more than one entity.
    """
    matches: list[tuple[str, ResolvedReference]] = []
    if name in system.variables:
        matches.append(("variable", ResolvedReference(name, VARIABLE, name)))
    if name in system.constants:
        matches.append(
            ("constant", _constant(name, name, system)),
        )
    if "." in name:
        lowered = name.replace(".", "__")
        if lowered in system.constants:
            matches.append(("FSM state", _constant(name, lowered, system)))
        imported = _imported(name, system)
        if imported is not None:
            matches.append(("imported input/output", imported))
    if name in system.aliases:
        matches.append(("alias", _alias(name, system)))

    if not matches:
        raise ValueError(f"Unknown reference '${{{name}}}'")
    if len(matches) > 1:
        kinds = ", ".join(kind for kind, _ in matches)
        raise ValueError(f"Ambiguous reference '${{{name}}}' matches: {kinds}")
    return matches[0][1]


def _constant(name: str, constant: str, system: "NncSystem") -> ResolvedReference:
    return ResolvedReference(
        name, CONSTANT, constant, value=float(system.constants[constant].value)
    )


def _imported(name: str, system: "NncSystem") -> ResolvedReference | None:
    head, _, port = name.partition(".")
    for item in system.imports:
        if item.alias != head or item.system is None:
            continue
        ports = set(item.system.input_variables) | set(item.system.output_variables)
        if port in ports:
            return ResolvedReference(name, IMPORTED, name)
    return None


def _alias(name: str, system: "NncSystem") -> ResolvedReference:
    expression = system.aliases[name]
    if isinstance(expression, VariableExpression):
        return ResolvedReference(
            name, VARIABLE, expression.variable.name, alias=name
        )
    if isinstance(expression, ReferenceExpression):
        target = ".".join(expression.parts)
        if _imported(target, system) is None:
            raise ValueError(
                f"Alias '{name}' target '{target}' is not an imported input or output"
            )
        return ResolvedReference(name, IMPORTED, target, alias=name)
    raise ValueError(
        f"Alias '{name}' must reference a variable or imported input/output"
    )
