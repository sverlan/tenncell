"""TENNCell YAML rule lowering."""

from ....parser.ast import BooleanConstantExpression, BooleanExpression, Expression
from ....parser.ast.value import FloatValue
from ....parser.ast.variable import Variable
from ....model.rule import Rule
from .common import (
    combine_guards,
    guard_negation,
    normalize_rule_items,
    parse_structured_rule,
    with_guard,
)


def lower_rule_items(
    raw_items,
    variables: dict[str, Variable],
    constants: dict[str, FloatValue],
    aliases: dict[str, Expression],
    accumulated_guard: BooleanExpression | None = None,
) -> list[Rule]:
    """Lower YAML rule items into model rules."""
    lowered: list[Rule] = []
    current_guard = accumulated_guard or BooleanConstantExpression(True)

    for item in normalize_rule_items(raw_items):
        if isinstance(item, str):
            from ....parser import parse_rule

            rule = parse_rule(item, variables, constants, aliases)
            lowered.append(with_guard(rule, current_guard))
            continue

        if not isinstance(item, dict):
            raise ValueError(f"Unsupported rule item type: {type(item).__name__}")

        if "if" in item:
            from ....parser import parse_condition

            condition = parse_condition(item["if"], variables, constants, aliases)
            then_guard = combine_guards(current_guard, condition)
            lowered.extend(
                lower_rule_items(
                    item.get("then"), variables, constants, aliases, then_guard
                )
            )
            if "else" in item:
                else_guard = combine_guards(current_guard, guard_negation(condition))
                lowered.extend(
                    lower_rule_items(
                        item.get("else"), variables, constants, aliases, else_guard
                    )
                )
            continue

        rule = parse_structured_rule(item, variables, constants, aliases)
        lowered.append(with_guard(rule, current_guard))

    return lowered
