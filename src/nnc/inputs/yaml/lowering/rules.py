"""TENNCell YAML rule lowering."""

from ....parser.ast import BooleanConstantExpression, BooleanExpression, Expression
from ....parser.ast.value import FloatValue
from ....parser.ast.variable import Variable
from ....model.rule import Rule
from ..locations import YamlLocationIndex
from .common import (
    attach_rule_location,
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
    *,
    source_origin: tuple[object, ...] | None = None,
    locations: YamlLocationIndex | None = None,
) -> list[Rule]:
    """Lower YAML rule items into model rules."""
    lowered: list[Rule] = []
    current_guard = accumulated_guard or BooleanConstantExpression(True)

    for index, item in enumerate(normalize_rule_items(raw_items)):
        item_origin = source_origin
        if source_origin is not None and isinstance(raw_items, list):
            item_origin = (*source_origin, index)
        if isinstance(item, str):
            from ....parser import parse_rule

            rule = parse_rule(item, variables, constants, aliases)
            rule = with_guard(rule, current_guard)
            attach_rule_location(rule, locations, item_origin)
            lowered.append(rule)
            continue

        if not isinstance(item, dict):
            raise ValueError(f"Unsupported rule item type: {type(item).__name__}")

        if "if" in item:
            from ....parser import parse_condition

            condition = parse_condition(item["if"], variables, constants, aliases)
            then_guard = combine_guards(current_guard, condition)
            lowered.extend(
                lower_rule_items(
                    item.get("then"),
                    variables,
                    constants,
                    aliases,
                    then_guard,
                    source_origin=(
                        (*item_origin, "then") if item_origin is not None else None
                    ),
                    locations=locations,
                )
            )
            if "else" in item:
                else_guard = combine_guards(current_guard, guard_negation(condition))
                lowered.extend(
                    lower_rule_items(
                        item.get("else"),
                        variables,
                        constants,
                        aliases,
                        else_guard,
                        source_origin=(
                            (*item_origin, "else") if item_origin is not None else None
                        ),
                        locations=locations,
                    )
                )
            continue

        rule = parse_structured_rule(item, variables, constants, aliases)
        rule = with_guard(rule, current_guard)
        attach_rule_location(rule, locations, item_origin)
        lowered.append(rule)

    return lowered
