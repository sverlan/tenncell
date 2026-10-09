"""Render bound property conditions as text in a backend's expression syntax."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from ...parser.ast import (
    BooleanAndExpression,
    BooleanConstantExpression,
    BooleanEqualTestExpression,
    BooleanExpression,
    BooleanGreaterEqualTestExpression,
    BooleanGreaterTestExpression,
    BooleanLessEqualTestExpression,
    BooleanLessTestExpression,
    BooleanNotEqualTestExpression,
    BooleanNotExpression,
    BooleanOrExpression,
    ConstantExpression,
    DifferenceExpression,
    DivisionExpression,
    Expression,
    IntDivisionExpression,
    IntMultiplicationExpression,
    MultiplicationExpression,
    ReferenceExpression,
    SumExpression,
    UnaryMinusExpression,
    VariableExpression,
)

_COMPARISONS: dict[type, str] = {
    BooleanLessTestExpression: "<",
    BooleanLessEqualTestExpression: "<=",
    BooleanGreaterTestExpression: ">",
    BooleanGreaterEqualTestExpression: ">=",
    BooleanEqualTestExpression: "==",
    BooleanNotEqualTestExpression: "!=",
}
_ARITHMETIC: dict[type, str] = {
    SumExpression: "+",
    DifferenceExpression: "-",
    MultiplicationExpression: "*",
    DivisionExpression: "/",
}


@dataclass(frozen=True, slots=True)
class ConditionSyntax:
    """Operator spellings and leaf renderers of one backend.

    Args:
        operators: Spelling of each TENNCell operator, keyed by its TENNCell
            spelling: ``&&``, ``||``, ``==``, ``!=``, ``<``, ``<=``, ``>``,
            ``>=``, ``+``, ``-``, ``*``, ``/``.
        negation: Prefix applied to the parenthesized operand of ``!``. Unary
            minus is always rendered as ``-(...)``; negative literals as ``(-n)``.
        true: Spelling of ``true``.
        false: Spelling of ``false``.
        column: Renders a trace column name (``alias__port`` for imported IO).
        literal: Renders a finite number.
    """

    operators: dict[str, str]
    negation: str
    true: str
    false: str
    column: Callable[[str], str]
    literal: Callable[[float], str]


def render_condition(
    node: BooleanExpression, syntax: ConditionSyntax, states: dict[str, float]
) -> str:
    """Render a bound condition; every binary operation is parenthesized.

    Args:
        node: Parsed condition from a ``BoundProperty``.
        syntax: Target backend syntax.
        states: FSM state values keyed by reference (``BoundProperty.states``).

    Returns:
        The condition text.

    Raises:
        ValueError: For a function call or an unsupported node; callers check
            backend support first.
    """
    if isinstance(node, BooleanConstantExpression):
        return syntax.true if node.value else syntax.false
    if isinstance(node, BooleanNotExpression):
        return f"{syntax.negation}({render_condition(node.expression, syntax, states)})"
    if isinstance(node, (BooleanAndExpression, BooleanOrExpression)):
        junction = "&&" if isinstance(node, BooleanAndExpression) else "||"
        left = render_condition(node.left, syntax, states)
        right = render_condition(node.right, syntax, states)
        return f"({left} {syntax.operators[junction]} {right})"
    operator = _COMPARISONS.get(type(node))
    if operator is not None:
        left = _render_value(node.left, syntax, states)  # type: ignore[attr-defined]
        right = _render_value(node.right, syntax, states)  # type: ignore[attr-defined]
        return f"({left} {syntax.operators[operator]} {right})"
    raise ValueError(f"Unsupported condition node: {type(node).__name__}")


def _render_value(
    node: Expression, syntax: ConditionSyntax, states: dict[str, float]
) -> str:
    if isinstance(node, ConstantExpression):
        return _literal(float(node.value.value), syntax)  # type: ignore[attr-defined]
    if isinstance(node, VariableExpression):
        return syntax.column(node.variable.name)
    if isinstance(node, ReferenceExpression):
        reference = ".".join(node.parts)
        if reference in states:
            return _literal(states[reference], syntax)
        return syntax.column("__".join(node.parts))
    if isinstance(node, UnaryMinusExpression):
        return f"-({_render_value(node.expression, syntax, states)})"
    if isinstance(node, (IntMultiplicationExpression, IntDivisionExpression)):
        scaling = "*" if isinstance(node, IntMultiplicationExpression) else "/"
        value = _render_value(node.expression, syntax, states)
        constant = _literal(float(node.constant), syntax)
        return f"({value} {syntax.operators[scaling]} {constant})"
    operator = _ARITHMETIC.get(type(node))
    if operator is not None:
        left = _render_value(node.left, syntax, states)  # type: ignore[attr-defined]
        right = _render_value(node.right, syntax, states)  # type: ignore[attr-defined]
        return f"({left} {syntax.operators[operator]} {right})"
    raise ValueError(f"Unsupported expression node: {type(node).__name__}")


def decimal_literal(value: float) -> str:
    """Render a finite number as plain decimal text without exponent notation.

    Raises:
        ValueError: If the value is not finite.
    """
    if not math.isfinite(value):
        raise ValueError(f"Cannot render non-finite constant {value}")
    if value.is_integer():
        return str(int(value))
    return format(Decimal(repr(value)), "f")


def _literal(value: float, syntax: ConditionSyntax) -> str:
    text = syntax.literal(value)
    return f"({text})" if value < 0 else text
