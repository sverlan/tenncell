"""TENNCell YAML FSM lowering."""

from ....parser import parse_condition, parse_rule
from ....parser.ast import BooleanConstantExpression, BooleanExpression, Expression
from ....parser.ast.value import FloatValue
from ....parser.ast.variable import Variable
from ....model.rule import Rule
from .common import (
    combine_guards,
    guard_negation,
    make_transition_rule,
    normalize_rule_items,
    parse_structured_rule,
    with_guard,
)


def build_state_constants(
    fsm_data: list[dict] | None,
    variables: dict[str, Variable],
    constants: dict[str, FloatValue],
) -> tuple[dict[str, dict[str, str]], list[tuple[str, str]]]:
    """Generate FSM state constants and initialization assignments."""
    fsm_constants: dict[str, dict[str, str]] = {}
    fsm_initializers: list[tuple[str, str]] = []
    seen_fsm_names: set[str] = set()
    seen_fsm_variables: set[str] = set()

    for fsm_entry in fsm_data or []:
        fsm_name = fsm_entry["name"]
        fsm_variable = fsm_entry["variable"]
        if fsm_name in seen_fsm_names:
            raise ValueError(f"Duplicate FSM name '{fsm_name}'")
        if fsm_variable in seen_fsm_variables:
            raise ValueError(f"Duplicate FSM variable '{fsm_variable}'")
        if fsm_variable not in variables:
            raise ValueError(f"FSM variable '{fsm_variable}' must be a local variable")
        seen_fsm_names.add(fsm_name)
        seen_fsm_variables.add(fsm_variable)

        states = fsm_entry.get("states", [])
        state_map: dict[str, str] = {}
        seen_state_names: set[str] = set()
        for index, state_entry in enumerate(states):
            if not isinstance(state_entry, dict) or len(state_entry) != 1:
                raise ValueError(f"FSM '{fsm_name}' states must be single-key mappings")
            state_name = next(iter(state_entry))
            if state_name in seen_state_names:
                raise ValueError(f"Duplicate state '{state_name}' in FSM '{fsm_name}'")
            seen_state_names.add(state_name)
            constant_name = f"{fsm_name}__{state_name}"
            if constant_name in constants:
                raise ValueError(
                    f"Generated FSM constant '{constant_name}' collides with an existing constant"
                )
            constants[constant_name] = FloatValue(index)
            state_map[state_name] = constant_name

        initial_state = fsm_entry["initial"]
        if initial_state not in state_map:
            raise ValueError(
                f"FSM '{fsm_name}' initial state '{initial_state}' is not declared"
            )
        fsm_constants[fsm_name] = state_map
        fsm_initializers.append((fsm_variable, state_map[initial_state]))

    return fsm_constants, fsm_initializers


def lower_fsm_rules(
    fsm_data: list[dict] | None,
    variables: dict[str, Variable],
    constants: dict[str, FloatValue],
    aliases: dict[str, Expression],
    fsm_constants: dict[str, dict[str, str]],
) -> list[Rule]:
    """Lower FSM rules into model rules and resolve state transitions."""
    lowered: list[Rule] = []

    for fsm_entry in fsm_data or []:
        fsm_name = fsm_entry["name"]
        fsm_variable_name = fsm_entry["variable"]
        fsm_variable = variables[fsm_variable_name]
        state_constant_map = fsm_constants[fsm_name]
        local_state_constants = {
            state_name: constants[constant_name]
            for state_name, constant_name in state_constant_map.items()
        }
        fsm_parse_constants = dict(constants)
        fsm_parse_constants.update(local_state_constants)

        def lower_state_items(
            raw_items, accumulated_guard: BooleanExpression
        ) -> list[Rule]:
            state_rules: list[Rule] = []
            for item in normalize_rule_items(raw_items):
                if isinstance(item, str):
                    rule = parse_rule(item, variables, fsm_parse_constants, aliases)
                    producer_text = item.rsplit("->", 1)[0]
                    if "|" in producer_text:
                        producer_text = producer_text.rsplit("|", 1)[1]
                    elif ":" in producer_text:
                        producer_text = producer_text.rsplit(":", 1)[1]
                    producer_text = producer_text.strip()
                    effective_guard = combine_guards(accumulated_guard, rule.guard)
                    if (
                        rule.consumer.name == fsm_variable_name
                        and producer_text in state_constant_map
                    ):
                        state_rules.append(
                            make_transition_rule(
                                fsm_variable,
                                state_constant_map[producer_text],
                                effective_guard,
                                variables,
                                constants,
                                aliases,
                            )
                        )
                    else:
                        state_rules.append(with_guard(rule, accumulated_guard))
                    continue

                if not isinstance(item, dict):
                    raise ValueError(
                        f"Unsupported FSM rule item type: {type(item).__name__}"
                    )

                if "if" in item:
                    condition = parse_condition(
                        item["if"], variables, fsm_parse_constants, aliases
                    )
                    then_guard = combine_guards(accumulated_guard, condition)
                    state_rules.extend(lower_state_items(item.get("then"), then_guard))
                    if "else" in item:
                        else_guard = combine_guards(
                            accumulated_guard, guard_negation(condition)
                        )
                        state_rules.extend(
                            lower_state_items(item.get("else"), else_guard)
                        )
                    continue

                consumer_name = item.get("consumer")
                producer_data = item.get("producer")
                if (
                    consumer_name == fsm_variable_name
                    and isinstance(producer_data, str)
                    and producer_data in state_constant_map
                ):
                    guard_data = item.get("guard", True)
                    if isinstance(guard_data, bool):
                        rule_guard = BooleanConstantExpression(guard_data)
                    else:
                        rule_guard = parse_condition(
                            guard_data, variables, fsm_parse_constants, aliases
                        )
                    state_rules.append(
                        make_transition_rule(
                            fsm_variable,
                            state_constant_map[producer_data],
                            combine_guards(accumulated_guard, rule_guard),
                            variables,
                            constants,
                            aliases,
                        )
                    )
                else:
                    rule = parse_structured_rule(
                        item, variables, fsm_parse_constants, aliases
                    )
                    state_rules.append(with_guard(rule, accumulated_guard))

            return state_rules

        for state_entry in fsm_entry.get("states", []):
            state_name = next(iter(state_entry))
            state_body = state_entry[state_name] or {}
            state_guard = parse_condition(
                f"{fsm_variable_name} == {state_constant_map[state_name]}",
                variables,
                fsm_parse_constants,
                aliases,
            )
            state_rules = lower_state_items(state_body.get("rules"), state_guard)

            transition_indexes = [
                index
                for index, rule in enumerate(state_rules)
                if rule.consumer.name == fsm_variable_name
            ]
            for pos, rule_index in enumerate(transition_indexes):
                rule = state_rules[rule_index]
                effective_guard = rule.guard
                for later_index in transition_indexes[pos + 1 :]:
                    effective_guard = combine_guards(
                        effective_guard, guard_negation(state_rules[later_index].guard)
                    )
                rule.guard = effective_guard

            lowered.extend(state_rules)

    return lowered
