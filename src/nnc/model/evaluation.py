"""Shared evaluation of TENNCell expressions against a value source.

The simulator (``NncSystem``) and the ``native`` verification checker evaluate
the same AST with the same operators, operand order, function-call order, and
short-circuit behavior; they differ only in where values come from.
"""

from __future__ import annotations

from typing import Protocol

from ..parser.ast import (
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
from ..parser.ast.expression import FunctionCallExpression
from ..parser.ast.value import FloatValue


class EvaluationContext(Protocol):
    """Value source used by ``evaluate_expression`` and ``evaluate_boolean``."""

    def variable_value(self, node: VariableExpression) -> FloatValue:
        """Return the value of a variable reference."""

    def reference_value(self, reference: str) -> FloatValue:
        """Return the value of a qualified reference such as ``sensor0.level``."""

    def call_function(self, name: str, arguments: list[float]) -> FloatValue:
        """Call a TENNCell function with already-evaluated arguments."""


def evaluate_expression(node: Expression, context: EvaluationContext) -> FloatValue:
    """Evaluate a TENNCell expression, reading values from ``context``.

    Args:
        node: TENNCell expression AST node.
        context: Source of variable, reference, and function values.

    Returns:
        The expression value.

    Raises:
        ValueError: If the node type is not supported.
    """
    if isinstance(node, ConstantExpression):
        return node.value  # type: ignore[return-value]
    if isinstance(node, VariableExpression):
        return context.variable_value(node)
    if isinstance(node, ReferenceExpression):
        return context.reference_value(".".join(node.parts))
    if isinstance(node, SumExpression):
        return evaluate_expression(node.left, context) + evaluate_expression(
            node.right, context
        )
    if isinstance(node, DifferenceExpression):
        return evaluate_expression(node.left, context) - evaluate_expression(
            node.right, context
        )
    if isinstance(node, MultiplicationExpression):
        return evaluate_expression(node.left, context) * evaluate_expression(
            node.right, context
        )
    if isinstance(node, DivisionExpression):
        return evaluate_expression(node.left, context) / evaluate_expression(
            node.right, context
        )
    if isinstance(node, UnaryMinusExpression):
        return -evaluate_expression(node.expression, context)
    if isinstance(node, IntMultiplicationExpression):
        value = evaluate_expression(node.expression, context)
        return value * type(value)(node.constant)
    if isinstance(node, IntDivisionExpression):
        value = evaluate_expression(node.expression, context)
        return value / type(value)(node.constant)
    if isinstance(node, FunctionCallExpression):
        arguments = [
            evaluate_expression(argument, context).value for argument in node.arguments
        ]
        return context.call_function(node.function_name, arguments)
    raise ValueError(f"Unsupported expression node at runtime: {type(node).__name__}")


def evaluate_boolean(node: BooleanExpression, context: EvaluationContext) -> bool:
    """Evaluate a TENNCell boolean expression, reading values from ``context``.

    ``&&`` and ``||`` short-circuit: the right operand is not evaluated when the
    left operand decides the result.

    Args:
        node: TENNCell boolean AST node.
        context: Source of variable, reference, and function values.

    Returns:
        The truth value.

    Raises:
        ValueError: If the node type is not supported.
    """
    if isinstance(node, BooleanConstantExpression):
        return node.value
    if isinstance(node, BooleanAndExpression):
        return evaluate_boolean(node.left, context) and evaluate_boolean(
            node.right, context
        )
    if isinstance(node, BooleanOrExpression):
        return evaluate_boolean(node.left, context) or evaluate_boolean(
            node.right, context
        )
    if isinstance(node, BooleanNotExpression):
        return not evaluate_boolean(node.expression, context)
    if isinstance(node, BooleanLessTestExpression):
        return evaluate_expression(node.left, context) < evaluate_expression(
            node.right, context
        )
    if isinstance(node, BooleanLessEqualTestExpression):
        return evaluate_expression(node.left, context) <= evaluate_expression(
            node.right, context
        )
    if isinstance(node, BooleanGreaterTestExpression):
        return evaluate_expression(node.left, context) > evaluate_expression(
            node.right, context
        )
    if isinstance(node, BooleanGreaterEqualTestExpression):
        return evaluate_expression(node.left, context) >= evaluate_expression(
            node.right, context
        )
    if isinstance(node, BooleanEqualTestExpression):
        return evaluate_expression(node.left, context) == evaluate_expression(
            node.right, context
        )
    if isinstance(node, BooleanNotEqualTestExpression):
        return evaluate_expression(node.left, context) != evaluate_expression(
            node.right, context
        )
    raise ValueError(f"Unsupported boolean node at runtime: {type(node).__name__}")
