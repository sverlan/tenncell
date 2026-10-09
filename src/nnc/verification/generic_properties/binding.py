"""Bind generic verification properties to a TENNCell system."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ...inputs.yaml.errors import YamlLocatedError
from ...inputs.yaml.locations import YamlLocationIndex
from ...parser import parse_condition
from ...parser.ast import BooleanExpression
from ...parser.ast.expression import (
    FunctionCallExpression,
    ReferenceExpression,
    VariableExpression,
)
from ...parser.ast.value.math_functions import MathFunctions
from ..config import GenericProperty
from ..references import _imported

if TYPE_CHECKING:
    from ...model.system import NncSystem

# Functions that never describe a recorded trace: they are re-drawn on evaluation.
NONDETERMINISTIC_FUNCTIONS = frozenset({"random"})


@dataclass(frozen=True, slots=True)
class BoundProperty:
    """A generic property whose conditions are parsed against the model.

    Args:
        property: The parsed property.
        condition: Parsed condition ``P``.
        trigger: Parsed trigger ``T`` for ``when`` kinds, else ``None``.
        columns: Trace columns the conditions read, trigger first, in first-use
            order. Imported inputs/outputs use ``alias__port``.
        functions: Names of the (deterministic, built-in) functions used.
        states: Values of the FSM states the conditions name, keyed by the
            reference as written (``ctrl.DONE``).
    """

    property: GenericProperty
    condition: BooleanExpression
    trigger: BooleanExpression | None
    columns: tuple[str, ...]
    functions: frozenset[str]
    states: dict[str, float] = field(default_factory=dict)


def bind_property(
    prop: GenericProperty, system: "NncSystem", locations: YamlLocationIndex
) -> BoundProperty:
    """Parse a property's conditions and check every name and function they use.

    Args:
        prop: Parsed generic property.
        system: Root TENNCell system the property belongs to.
        locations: Source locations used for errors.

    Returns:
        The bound property with its required columns and used functions.

    Raises:
        YamlLocatedError: If a condition does not parse, names an unknown
            reference, or calls a nondeterministic, unknown, or overridden function.
    """
    trigger = (
        _parse(prop, prop.trigger, "when", system, locations)
        if prop.trigger is not None
        else None
    )
    condition = _parse(prop, prop.condition, prop.condition_key, system, locations)
    columns: dict[str, None] = {}
    functions: set[str] = set()
    states: dict[str, float] = {}
    for key, expression in (("when", trigger), (prop.condition_key, condition)):
        if expression is None:
            continue
        for node in _walk(expression):
            _check_node(node, prop, key, system, locations, columns, functions, states)
    return BoundProperty(
        property=prop,
        condition=condition,
        trigger=trigger,
        columns=tuple(columns),
        functions=frozenset(functions),
        states=states,
    )


def _parse(
    prop: GenericProperty,
    text: str,
    key: str,
    system: "NncSystem",
    locations: YamlLocationIndex,
) -> BooleanExpression:
    try:
        parsed = parse_condition(
            text, system.variables, system.constants, system.aliases
        )
    except Exception as error:
        raise _error(
            locations, prop, key, f"invalid '{key}' condition '{text}': {error}"
        ) from error
    if not isinstance(parsed, BooleanExpression):
        raise _error(
            locations, prop, key, f"'{key}' condition '{text}' is not a condition"
        )
    return parsed


def _check_node(
    node: object,
    prop: GenericProperty,
    key: str,
    system: "NncSystem",
    locations: YamlLocationIndex,
    columns: dict[str, None],
    functions: set[str],
    states: dict[str, float],
) -> None:
    if isinstance(node, VariableExpression):
        columns.setdefault(node.variable.name, None)
    elif isinstance(node, ReferenceExpression):
        reference = ".".join(node.parts)
        is_fsm_state = "__".join(node.parts) in system.constants
        is_imported = _imported(reference, system) is not None
        if is_fsm_state and is_imported:
            raise _error(
                locations,
                prop,
                key,
                f"ambiguous reference '{reference}': it names both an FSM state "
                "and an imported input/output",
            )
        if is_fsm_state:  # FSM state constant such as ctrl.DONE
            states[reference] = float(system.constants["__".join(node.parts)].value)
            return
        if not is_imported:
            raise _error(
                locations,
                prop,
                key,
                f"unknown reference '{reference}': expected an FSM state or an "
                "imported input/output",
            )
        columns.setdefault("__".join(node.parts), None)
    elif isinstance(node, FunctionCallExpression):
        name = node.function_name
        if name in NONDETERMINISTIC_FUNCTIONS:
            raise _error(
                locations,
                prop,
                key,
                f"function '{name}' is not allowed in verification properties "
                "because it is nondeterministic",
            )
        if not MathFunctions._is_default_function(name):
            raise _error(
                locations,
                prop,
                key,
                f"function '{name}' is not allowed in verification properties: "
                "only unmodified built-in functions can be used",
            )
        functions.add(name)


def _walk(node: object) -> Iterator[object]:
    """Yield AST nodes depth-first, left operand before right operand."""
    yield node
    for attribute in ("left", "right", "expression"):
        child = getattr(node, attribute, None)
        if child is not None and not isinstance(child, (int, float)):
            yield from _walk(child)
    for argument in getattr(node, "arguments", []):
        yield from _walk(argument)


def _error(
    locations: YamlLocationIndex, prop: GenericProperty, key: str, message: str
) -> YamlLocatedError:
    return locations.error(
        f"Verification property '{prop.id}': {message}", *prop.yaml_path, key
    )
