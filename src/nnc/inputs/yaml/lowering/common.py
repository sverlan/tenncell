"""Shared TENNCell YAML lowering helpers."""

from collections.abc import Iterable

from ....parser import parse_condition, parse_expression
from ....parser.ast import (
    BooleanAndExpression,
    BooleanConstantExpression,
    BooleanExpression,
    BooleanNotExpression,
    Expression,
)
from ....parser.ast.value import FloatValue
from ....parser.ast.variable import Variable
from ....model.rule import Rule


def register_initial_declarations(
    initial_declarations: dict[str, tuple[int, int]],
    variable_names: Iterable[str],
    cell_index: int,
    content_index: int,
) -> None:
    """Reject duplicate module-level variable initializers."""
    for variable_name in variable_names:
        first_location = initial_declarations.get(variable_name)
        if first_location is not None:
            first_cell_index, first_content_index = first_location
            raise ValueError(
                f"Duplicate initial declaration for variable '{variable_name}' "
                f"first declared at cells[{first_cell_index}].contents"
                f"[{first_content_index}]"
            )
        initial_declarations[variable_name] = (cell_index, content_index)


def normalize_rule_items(raw_items) -> list:
    """Normalize a YAML rule payload into a list of items."""
    if raw_items is None:
        return []
    if isinstance(raw_items, list):
        return raw_items
    return [raw_items]


def combine_guards(
    left: BooleanExpression, right: BooleanExpression
) -> BooleanExpression:
    """Combine two guard expressions with logical AND semantics."""
    if isinstance(left, BooleanConstantExpression) and left.value is True:
        return right
    if isinstance(right, BooleanConstantExpression) and right.value is True:
        return left
    return BooleanAndExpression(left, right)


def guard_negation(guard: BooleanExpression) -> BooleanExpression:
    """Return the logical negation of a guard expression."""
    if isinstance(guard, BooleanConstantExpression):
        return BooleanConstantExpression(not guard.value)
    return BooleanNotExpression(guard)


def parse_structured_rule(
    rule_data: dict,
    variables: dict[str, Variable],
    constants: dict[str, FloatValue],
    aliases: dict[str, Expression],
) -> Rule:
    """Lower a structured rule mapping into a model rule."""
    guard_data = rule_data.get("guard", True)
    if isinstance(guard_data, bool):
        guard = BooleanConstantExpression(guard_data)
    else:
        guard = parse_condition(guard_data, variables, constants, aliases)

    producer_data = rule_data.get("producer")
    producer = parse_expression(producer_data, variables, constants, aliases)

    consumer_variable_name = rule_data.get("consumer")
    consumer = variables.get(consumer_variable_name)
    if consumer is None:
        raise ValueError(
            f"Variable {consumer_variable_name} not defined in the context"
        )
    return Rule(consumer, producer, guard)


def with_guard(rule: Rule, extra_guard: BooleanExpression) -> Rule:
    """Attach an additional guard condition to a lowered rule."""
    return Rule(rule.consumer, rule.producer, combine_guards(extra_guard, rule.guard))


def make_transition_rule(
    consumer: Variable,
    target_constant_name: str,
    guard: BooleanExpression,
    variables: dict[str, Variable],
    constants: dict[str, FloatValue],
    aliases: dict[str, Expression],
) -> Rule:
    """Create a transition rule that assigns a generated FSM state constant."""
    producer = parse_expression(
        f"({consumer.name} * 0) + {target_constant_name}", variables, constants, aliases
    )
    return Rule(consumer, producer, guard)
