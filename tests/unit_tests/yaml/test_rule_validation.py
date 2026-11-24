"""YAML loader contracts for rule structure and writable destinations."""

import pytest

from nnc.inputs.yaml.errors import YamlLocatedError
from nnc.model.system import NncSystem


@pytest.mark.parametrize("item, type_name", [("null", "NoneType"), ("[]", "list")])
def test_top_level_rule_items_reject_null_and_nested_lists(tmp_path, item, type_name):
    """A top-level rules entry must be a rule string or a mapping."""
    model = tmp_path / "bad_rule.yaml"
    model.write_text(f"rules:\n  - {item}\n", encoding="utf-8")

    with pytest.raises(ValueError, match=f"Unsupported rule item type: {type_name}"):
        NncSystem.from_yaml(str(model))


@pytest.mark.parametrize("zero_reset_mode", [False, True])
@pytest.mark.parametrize(
    "rules",
    [
        "  - s1 -> s1\n",
        "  - x -> s1\n",
        "  - False | x -> s1\n",
        "  - {guard: true, producer: x, consumer: s1}\n",
        "  - if: x > 0\n    then:\n      - x -> s1\n",
        "  - if: x > 0\n    then: x -> x\n    else: x -> s1\n",
        "  - repeat:\n      var: i\n      range: [1, 1]\n"
        "      body:\n        - x -> s${i}\n",
    ],
    ids=["self-loop", "internal-source", "disabled", "structured", "if", "else", "repeat"],
)
def test_input_destinations_are_rejected_with_rule_location(
    tmp_path, zero_reset_mode, rules
):
    """Every rule form rejects input destinations, even when inactive."""
    model = tmp_path / "input_destination.yaml"
    document = (
        f"module:\n  zero_reset_mode: {str(zero_reset_mode).lower()}\n"
        "cells:\n  - id: 1\n    contents:\n      - s1 = 0, x = 1\n"
        "    input: [s1]\nrules:\n" + rules
    )
    model.write_text(document, encoding="utf-8")

    with pytest.raises(YamlLocatedError, match="destination 's1' is an input") as exc:
        NncSystem.from_yaml(str(model))

    assert exc.value.source_path == model.resolve()
    assert exc.value.line is not None
    # Generated rules retain the physical template line for their destination.
    expected_line = next(
        i for i, line in enumerate(document.splitlines(), start=1)
        if "-> s1" in line or "consumer: s1" in line or "-> s${i}" in line
    )
    assert exc.value.line == expected_line


@pytest.mark.parametrize("zero_reset_mode", [False, True])
@pytest.mark.parametrize(
    "rule", ["1 -> s1", "{guard: true, producer: '1', consumer: s1}"],
    ids=["plain", "structured"],
)
def test_input_destinations_from_fsm_rules_are_rejected(tmp_path, zero_reset_mode, rule):
    """FSM lowering cannot bypass destination validation."""
    model = tmp_path / "fsm_input_destination.yaml"
    document = (
        f"module:\n  zero_reset_mode: {str(zero_reset_mode).lower()}\n"
        "cells:\n  - id: 1\n    contents:\n      - s1 = 0, state = 0\n"
        "    input: [s1]\n"
        "fsm:\n  - name: ctrl\n    variable: state\n    initial: IDLE\n"
        f"    states:\n      - IDLE:\n          rules:\n            - {rule}\n"
    )
    model.write_text(document, encoding="utf-8")

    with pytest.raises(YamlLocatedError, match="destination 's1' is an input") as exc:
        NncSystem.from_yaml(str(model))

    assert exc.value.source_path == model.resolve()
    assert exc.value.line == len(document.splitlines())


def test_input_destination_in_include_reports_the_included_file(tmp_path):
    """Rejection retains the physical location of an included rule."""
    fragment = tmp_path / "rules.yaml"
    fragment.write_text("rules:\n  - 1 -> s1\n", encoding="utf-8")
    model = tmp_path / "main.yaml"
    model.write_text(
        "module:\n  include: [rules.yaml]\n"
        "cells:\n  - id: 1\n    contents:\n      - s1 = 0\n    input: [s1]\n",
        encoding="utf-8",
    )

    with pytest.raises(YamlLocatedError, match="destination 's1' is an input") as exc:
        NncSystem.from_yaml(str(model))

    assert exc.value.source_path == fragment.resolve()
    assert exc.value.line == 2


@pytest.mark.parametrize("zero_reset_mode", [False, True])
def test_inputs_remain_readable_in_guards_and_productions(tmp_path, zero_reset_mode):
    """Input fan-out and internal/output destinations remain valid."""
    model = tmp_path / "input_source.yaml"
    model.write_text(
        f"module:\n  zero_reset_mode: {str(zero_reset_mode).lower()}\n"
        "cells:\n  - id: 1\n    contents:\n      - s1 = 0, x = 0, y = 0\n"
        "    input: [s1]\n    output: [y]\n"
        "rules:\n  - s1 > 0 | s1 -> x\n  - s1 -> y\n",
        encoding="utf-8",
    )
    system = NncSystem.from_yaml(str(model))

    system.step({"s1": 3.0})

    assert float(system.variables["x"].value.value) == 3.0
    assert float(system.variables["y"].value.value) == 3.0
    assert float(system.variables["s1"].value.value) == (3.0 if zero_reset_mode else 0.0)


def test_missing_rule_location_falls_back_to_the_rules_section(tmp_path, monkeypatch):
    """Input rejection still identifies the YAML file if rule metadata is absent."""
    model = tmp_path / "missing_location.yaml"
    document = (
        "cells:\n  - id: 1\n    contents:\n      - s1 = 0\n"
        "    input: [s1]\nrules:\n  - 1 -> s1\n"
    )
    model.write_text(document, encoding="utf-8")
    add_rule = NncSystem.add_rule

    def add_without_location(system, rule):
        rule.source_location = None
        add_rule(system, rule)

    monkeypatch.setattr(NncSystem, "add_rule", add_without_location)

    with pytest.raises(YamlLocatedError, match="destination 's1' is an input") as exc:
        NncSystem.from_yaml(str(model))

    assert exc.value.source_path == model.resolve()
    assert exc.value.line == len(document.splitlines())


def test_located_repeat_error_retains_its_message_without_a_wrapper(tmp_path):
    """Other located lowering errors follow the documented diagnostic policy."""
    model = tmp_path / "bad_repeat.yaml"
    model.write_text(
        "rules:\n  - repeat:\n      var: i\n      range: [1, 1]\n"
        "      body:\n        - x_${missing} -> x\n",
        encoding="utf-8",
    )

    with pytest.raises(YamlLocatedError) as exc:
        NncSystem.from_yaml(str(model))

    assert exc.value.message == "Unknown repeat placeholder 'missing'"
    assert exc.value.source_path == model.resolve()
    assert exc.value.line is not None
    assert "Error lowering YAML rules" not in str(exc.value)


def test_input_destination_in_import_reports_the_imported_file(tmp_path):
    """An imported module's invalid destination is diagnosed in that module."""
    child = tmp_path / "child.yaml"
    child.write_text(
        "cells:\n  - id: 1\n    contents:\n      - s1 = 0\n"
        "    input: [s1]\nrules:\n  - 1 -> s1\n",
        encoding="utf-8",
    )
    model = tmp_path / "main.yaml"
    model.write_text(
        "imports:\n  - module: child.yaml\n    as: child\n",
        encoding="utf-8",
    )

    with pytest.raises(YamlLocatedError, match="destination 's1' is an input") as exc:
        NncSystem.from_yaml(str(model))

    assert exc.value.source_path == child.resolve()
    assert exc.value.line == 7
