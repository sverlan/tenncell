"""Internal contract tests for YAML lowering helpers."""

import pytest

from nnc.inputs.yaml.lowering.common import (
    combine_guards,
    guard_negation,
    make_transition_rule,
    normalize_rule_items,
    parse_structured_rule,
    with_guard,
)
from nnc.inputs.yaml.lowering.fsm import build_state_constants, lower_fsm_rules
from nnc.inputs.yaml.lowering.rules import lower_rule_items
from nnc.parser.ast import (
    BooleanAndExpression,
    BooleanConstantExpression,
    BooleanNotExpression,
    Variable,
)
from nnc.parser.ast.value import FloatValue


class TestYamlLoweringHelpers:
    def test_common_helpers_cover_basic_branches(self):
        variables = {
            "x": Variable("x", FloatValue(0.0)),
            "y": Variable("y", FloatValue(0.0)),
        }
        constants = {"BASE": FloatValue(1.0)}
        aliases = {}

        assert normalize_rule_items(None) == []
        assert normalize_rule_items("x -> y") == ["x -> y"]

        always = BooleanConstantExpression(True)
        guard = BooleanConstantExpression(False)

        assert combine_guards(always, guard) is guard
        assert combine_guards(guard, always) is guard
        assert isinstance(
            combine_guards(
                BooleanConstantExpression(False), BooleanConstantExpression(False)
            ),
            BooleanAndExpression,
        )

        negated = guard_negation(always)
        assert isinstance(negated, BooleanConstantExpression)
        assert negated.value is False
        assert isinstance(guard_negation(guard), BooleanConstantExpression)
        assert guard_negation(guard).value is True

        rule = parse_structured_rule(
            {"consumer": "x", "producer": "y", "guard": True},
            variables,
            constants,
            aliases,
        )
        assert rule.consumer.name == "x"
        assert rule.guard.value is True

        wrapped = with_guard(rule, BooleanConstantExpression(False))
        assert wrapped.consumer.name == "x"
        assert isinstance(wrapped.guard, BooleanConstantExpression)
        assert wrapped.guard.value is False

        transition = make_transition_rule(
            variables["x"],
            "BASE",
            BooleanConstantExpression(True),
            variables,
            constants,
            aliases,
        )
        assert transition.consumer.name == "x"
        assert transition.guard.value is True

        with pytest.raises(ValueError, match="not defined"):
            parse_structured_rule(
                {"consumer": "missing", "producer": "y"}, variables, constants, aliases
            )

    def test_build_state_constants_validates_and_initializes(self):
        variables = {
            "ctrl_state": Variable("ctrl_state", FloatValue(0.0)),
            "x": Variable("x", FloatValue(0.0)),
            "y": Variable("y", FloatValue(0.0)),
        }
        constants = {}
        fsm_data = [
            {
                "name": "ctrl",
                "variable": "ctrl_state",
                "initial": "IDLE",
                "states": [
                    {"IDLE": {}},
                    {"RUN": {}},
                ],
            }
        ]

        fsm_constants, initializers = build_state_constants(
            fsm_data, variables, constants
        )

        assert fsm_constants["ctrl"]["IDLE"] == "ctrl__IDLE"
        assert fsm_constants["ctrl"]["RUN"] == "ctrl__RUN"
        assert initializers == [("ctrl_state", "ctrl__IDLE")]
        assert constants["ctrl__IDLE"].value == 0
        assert constants["ctrl__RUN"].value == 1

    @pytest.mark.parametrize(
        ("fsm_data", "message"),
        [
            (
                [
                    {
                        "name": "ctrl",
                        "variable": "ctrl_state",
                        "initial": "IDLE",
                        "states": [{"IDLE": {}}],
                    },
                    {
                        "name": "ctrl",
                        "variable": "other",
                        "initial": "IDLE",
                        "states": [{"IDLE": {}}],
                    },
                ],
                "Duplicate FSM name",
            ),
            (
                [
                    {
                        "name": "ctrl",
                        "variable": "ctrl_state",
                        "initial": "IDLE",
                        "states": [{"IDLE": {}}],
                    },
                    {
                        "name": "other",
                        "variable": "ctrl_state",
                        "initial": "IDLE",
                        "states": [{"IDLE": {}}],
                    },
                ],
                "Duplicate FSM variable",
            ),
            (
                [
                    {
                        "name": "ctrl",
                        "variable": "missing",
                        "initial": "IDLE",
                        "states": [{"IDLE": {}}],
                    }
                ],
                "must be a local variable",
            ),
            (
                [
                    {
                        "name": "ctrl",
                        "variable": "ctrl_state",
                        "initial": "IDLE",
                        "states": [{"IDLE": {}}, {"IDLE": {}}],
                    }
                ],
                "Duplicate state",
            ),
            (
                [
                    {
                        "name": "ctrl",
                        "variable": "ctrl_state",
                        "initial": "MISSING",
                        "states": [{"IDLE": {}}],
                    }
                ],
                "initial state",
            ),
            (
                [
                    {
                        "name": "ctrl",
                        "variable": "ctrl_state",
                        "initial": "IDLE",
                        "states": [{"IDLE": {}, "RUN": {}}],
                    }
                ],
                "single-key mappings",
            ),
        ],
    )
    def test_build_state_constants_rejects_invalid_fsm_shapes(self, fsm_data, message):
        variables = {"ctrl_state": Variable("ctrl_state", FloatValue(0.0))}
        constants = {}

        with pytest.raises(ValueError, match=message):
            build_state_constants(fsm_data, variables, constants)

    def test_lower_fsm_rules_handles_transitions_and_branches(self):
        variables = {
            "ctrl_state": Variable("ctrl_state", FloatValue(0.0)),
            "x": Variable("x", FloatValue(0.0)),
            "y": Variable("y", FloatValue(0.0)),
        }
        constants = {}
        aliases = {}
        fsm_data = [
            {
                "name": "ctrl",
                "variable": "ctrl_state",
                "initial": "IDLE",
                "states": [
                    {
                        "IDLE": {
                            "rules": [
                                "RUN -> ctrl_state",
                                {
                                    "if": "x > 2",
                                    "then": [
                                        {"consumer": "y", "producer": "1"},
                                    ],
                                    "else": [
                                        {"consumer": "y", "producer": "0"},
                                    ],
                                },
                                {
                                    "consumer": "ctrl_state",
                                    "producer": "RUN",
                                    "guard": "x > 0",
                                },
                                {
                                    "consumer": "ctrl_state",
                                    "producer": "IDLE",
                                    "guard": "y > 0",
                                },
                            ]
                        }
                    },
                    {
                        "RUN": {
                            "rules": [
                                {"consumer": "ctrl_state", "producer": "IDLE"},
                            ]
                        }
                    },
                ],
            }
        ]

        fsm_constants, _ = build_state_constants(fsm_data, variables, constants)
        lowered = lower_fsm_rules(
            fsm_data, variables, constants, aliases, fsm_constants
        )

        assert any(rule.consumer.name == "ctrl_state" for rule in lowered)
        assert any(rule.consumer.name == "y" for rule in lowered)
        assert len(lowered) >= 4
        assert any(
            rule.consumer.name == "ctrl_state" and "!" in str(rule.guard)
            for rule in lowered
        )

    def test_lower_fsm_and_rule_helpers_cover_remaining_branch_cases(self):
        variables = {
            "ctrl_state": Variable("ctrl_state", FloatValue(0.0)),
            "x": Variable("x", FloatValue(0.0)),
            "y": Variable("y", FloatValue(0.0)),
        }
        constants = {"ctrl__IDLE": FloatValue(9.0)}
        aliases = {}

        with pytest.raises(ValueError, match="collides with an existing constant"):
            build_state_constants(
                [
                    {
                        "name": "ctrl",
                        "variable": "ctrl_state",
                        "initial": "IDLE",
                        "states": [
                            {"IDLE": {}},
                        ],
                    }
                ],
                variables,
                constants,
            )

        constants = {}
        fsm_data = [
            {
                "name": "ctrl",
                "variable": "ctrl_state",
                "initial": "IDLE",
                "states": [
                    {
                        "IDLE": {
                            "rules": [
                                "x > 0 | 1 -> y",
                                "x > 0 : 2 -> y",
                                {
                                    "if": "x > 0",
                                    "then": [
                                        "x > 0 | 3 -> y",
                                    ],
                                    "else": [
                                        "x > 0 : 4 -> y",
                                    ],
                                },
                                123,
                            ]
                        }
                    }
                ],
            }
        ]

        fsm_constants, _ = build_state_constants(fsm_data, variables, constants)
        with pytest.raises(ValueError, match="Unsupported FSM rule item type"):
            lower_fsm_rules(fsm_data, variables, constants, aliases, fsm_constants)

        rule_items = [
            {
                "if": "x > 0",
                "then": [
                    "x -> y",
                ],
                "else": [
                    "y -> x",
                ],
            }
        ]
        lowered = lower_rule_items(rule_items, variables, constants, aliases)
        assert len(lowered) == 2
        assert lowered[0].consumer.name == "y"
        assert lowered[1].consumer.name == "x"

        lowered = lower_rule_items(
            ["x > 0 | 1 -> y", "x > 0 : 2 -> y"], variables, constants, aliases
        )
        assert len(lowered) == 2
        assert all(rule.consumer.name == "y" for rule in lowered)

        lowered = lower_rule_items(
            [
                {
                    "if": "x > 0",
                    "then": ["x -> y"],
                }
            ],
            variables,
            constants,
            aliases,
        )
        assert len(lowered) == 1

        with pytest.raises(ValueError, match="Unsupported rule item type"):
            lower_rule_items([123], variables, constants, aliases)
