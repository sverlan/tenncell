"""Contract tests for parsing and binding generic verification properties."""

from pathlib import Path

import pytest

from nnc import NncSystem
from nnc.inputs.yaml.errors import YamlLocatedError
from nnc.inputs.yaml.locations import load_yaml_data_and_locations
from nnc.inputs.yaml.sections import YamlSectionContext
from nnc.parser.ast.value.math_functions import MathFunctions
from nnc.verification import GenericProperty, parse_verification_section
from nnc.verification.binding import bind_verification
from nnc.verification.generic_properties.binding import bind_property

REFERENCES = (
    Path(__file__).resolve().parents[2] / "fixtures" / "verification" / "references"
)
MODEL = (
    "cells:\n  - id: 1\n    contents:\n      - x = 0, t = 0\n    input: [t]\n"
    "    output: [x]\n"
    "rules:\n  - x + 1 -> x\n"
)


def _parse(tmp_path: Path, properties: str):
    path = tmp_path / "model.yaml"
    path.write_text(
        MODEL + "verification:\n  properties:\n" + properties, encoding="utf-8"
    )
    data, locations = load_yaml_data_and_locations(path)
    context = YamlSectionContext(path, [], {}, data, locations)
    return path, parse_verification_section(data["verification"], context)


@pytest.mark.parametrize(
    ("body", "kind", "condition", "trigger", "after", "within"),
    [
        ("      always: x >= 0\n", "always", "x >= 0", None, None, None),
        ("      never: x < 0\n", "never", "x < 0", None, None, None),
        ("      eventually: x > 2\n", "eventually", "x > 2", None, None, None),
        (
            "      eventually: x > 2\n      within: [1, 3]\n",
            "eventually_within",
            "x > 2",
            None,
            None,
            (1, 3),
        ),
        (
            "      when: t > 0\n      then: x > 1\n      after: 2\n",
            "response_after",
            "x > 1",
            "t > 0",
            2,
            None,
        ),
        (
            "      when: t > 0\n      then: x > 1\n      within: [0, 4]\n",
            "response_within",
            "x > 1",
            "t > 0",
            None,
            (0, 4),
        ),
        (
            "      when: t > 0\n      then_always: x > 1\n",
            "persistence",
            "x > 1",
            "t > 0",
            0,
            None,
        ),
        (
            "      when: t > 0\n      then_always: x > 1\n      after: 3\n",
            "persistence",
            "x > 1",
            "t > 0",
            3,
            None,
        ),
        ("      cover: x == 5\n", "cover", "x == 5", None, None, None),
        ("      always: true\n", "always", "true", None, None, None),
    ],
)
def test_parses_every_valid_kind(
    tmp_path, body, kind, condition, trigger, after, within
):
    _, config = _parse(tmp_path, "    - id: p\n" + body)

    (prop,) = config.properties
    assert (prop.kind, prop.condition, prop.trigger, prop.after, prop.within) == (
        kind,
        condition,
        trigger,
        after,
        within,
    )


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("      description: only text\n", r":11: .*defines no property kind"),
        (
            "      always: x\n      within: [1, 2]\n",
            r":11: .*invalid combination of keys always, within",
        ),
        (
            "      always: x\n      never: x\n",
            r":11: .*invalid combination of keys always, never",
        ),
        ("      when: t\n", r":11: .*'when' needs 'then' or 'then_always'"),
        (
            "      then: x\n      after: 1\n",
            r":11: .*'then'/'then_always' needs 'when'",
        ),
        (
            "      when: t\n      then: x\n",
            r":11: .*needs exactly one of 'after' or 'within'",
        ),
        (
            "      when: t\n      then: x\n      after: 1\n      within: [1, 2]\n",
            r":11: .*'after' and 'within' cannot be combined",
        ),
        (
            "      when: t\n      then: x\n      then_always: x\n      after: 1\n",
            r":11: .*'then' and 'then_always' cannot be combined",
        ),
        (
            "      when: t\n      then_always: x\n      within: [1, 2]\n",
            r":11: .*invalid combination of keys",
        ),
        (
            "      always:\n        always: x\n",
            r":13: .*nested properties are not supported",
        ),
        ('      always: ""\n', r":12: .*condition must be a non-empty string"),
        (
            "      when: t\n      then: x\n      after: -1\n",
            r":14: .*after must be a non-negative integer",
        ),
        (
            "      when: t\n      then: x\n      after: true\n",
            r":14: .*after must be a non-negative integer",
        ),
        (
            "      eventually: x\n      within: [3, 1]\n",
            r":13: .*within must be \[a, b\]",
        ),
        ("      eventually: x\n      within: [1]\n", r":13: .*within must be \[a, b\]"),
        (
            "      always: x\n      from_step: -2\n",
            r":13: .*from_step must be a non-negative integer",
        ),
        (
            "      always: x\n      probability: 0.9\n",
            r":13: .*'probability' is reserved",
        ),
        (
            "      always: x\n      label: q\n",
            r":13: Unknown key 'label' in verification property 'p'",
        ),
        (
            "      always: x\n      description: 3\n",
            r":13: .*description must be a string",
        ),
    ],
)
def test_rejects_invalid_properties(tmp_path, body, message):
    with pytest.raises(YamlLocatedError, match=message):
        _parse(tmp_path, "    - id: p\n" + body)


def _bind_text(tmp_path: Path, body: str):
    path, config = _parse(tmp_path, "    - id: p\n" + body)
    system = NncSystem.from_yaml(str(path))
    return bind_verification(config, system, system.source_locations)


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("      always: y > 0\n", r":12: .*invalid 'always' condition 'y > 0'"),
        ("      always: x >\n", r":12: .*invalid 'always' condition"),
        (
            "      when: q > 0\n      then: x > 0\n      after: 1\n",
            r":12: .*invalid 'when' condition",
        ),
        (
            "      always: random() < 2\n",
            r":12: .*function 'random' is not allowed.*nondeterministic",
        ),
        ("      always: ghost.level > 0\n", r":12: .*unknown reference 'ghost\.level'"),
    ],
)
def test_binding_rejects_bad_conditions(tmp_path, body, message):
    with pytest.raises(YamlLocatedError, match=message):
        _bind_text(tmp_path, body)


def test_binding_rejects_runtime_registered_function(tmp_path, monkeypatch):
    monkeypatch.setitem(MathFunctions._functions, "double_it", lambda value: 2 * value)
    monkeypatch.setitem(MathFunctions._function_arg_counts, "double_it", 1)

    with pytest.raises(
        YamlLocatedError,
        match=r":12: .*function 'double_it' is not allowed in verification properties",
    ):
        _bind_text(tmp_path, "      always: double_it(x) >= 0\n")


def test_binding_rejects_overridden_builtin_function(tmp_path, monkeypatch):
    monkeypatch.setitem(MathFunctions._functions, "min", lambda *values: 0.0)

    with pytest.raises(YamlLocatedError, match=r"function 'min' is not allowed"):
        _bind_text(tmp_path, "      always: min(x, 1) >= 0\n")


def test_binding_records_columns_and_functions(tmp_path):
    bound = _bind_text(
        tmp_path,
        "      when: t > 0\n      then: sqrt(x) + abs(t) >= 0\n      after: 1\n",
    )

    (prop,) = bound.properties
    assert prop.columns == ("t", "x")  # trigger first, then first use
    assert prop.functions == frozenset({"sqrt", "abs"})


def _prop(condition: str, **fields) -> GenericProperty:
    values = dict(
        id="p",
        kind="always",
        condition=condition,
        condition_key="always",
        trigger=None,
        after=None,
        within=None,
        from_step=0,
        targets=None,
        description=None,
        yaml_path=("verification", "properties", 0),
    )
    values.update(fields)
    return GenericProperty(**values)


@pytest.fixture(scope="module")
def references_system():
    return NncSystem.from_yaml(str(REFERENCES / "root.yaml"))


def test_binding_resolves_model_names(references_system):
    system = references_system
    bound = bind_property(
        _prop(
            "mode == ctrl.ALERT && sensed > LIMIT && current >= COUNT "
            "&& sensor0.raw >= 0"
        ),
        system,
        system.source_locations,
    )

    # FSM states and constants are values, not columns; aliases use their target.
    assert bound.columns == ("mode", "sensor0__level", "sample", "sensor0__raw")
    assert bound.functions == frozenset()
    assert bound.trigger is None


def test_binding_rejects_reference_that_is_both_fsm_state_and_imported_io():
    system = NncSystem.from_yaml(str(REFERENCES / "ambiguous.yaml"))

    with pytest.raises(
        YamlLocatedError,
        match=r"ambiguous reference 'ctrl\.level': it names both an FSM state",
    ):
        bind_property(_prop("ctrl.level > 0"), system, system.source_locations)


def test_binding_rejects_imported_internal_variable(references_system):
    system = references_system

    with pytest.raises(YamlLocatedError, match=r"unknown reference 'sensor0\.hidden'"):
        bind_property(_prop("sensor0.hidden > 0"), system, system.source_locations)
