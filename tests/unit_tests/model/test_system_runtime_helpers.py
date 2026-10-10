"""Internal contract tests for NncSystem runtime helper behavior."""

from pathlib import Path

import pytest

from nnc.inputs.yaml.module_config import ImportConfig, ModuleConfig
from nnc.model.cell import Cell
from nnc.model.system import NncSystem, ResolvedReference
from nnc.parser.ast import (
    BooleanAndExpression,
    BooleanConstantExpression,
    BooleanEqualTestExpression,
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
    IntDivisionExpression,
    IntMultiplicationExpression,
    MultiplicationExpression,
    ReferenceExpression,
    SumExpression,
    UnaryMinusExpression,
    Variable,
    VariableExpression,
)
from nnc.parser.ast.expression import FunctionCallExpression
from nnc.parser.ast.value import FloatValue
from nnc.model.rule import Rule


class TestSystemRuntimeHelpers:
    def _make_system(self) -> NncSystem:
        system = NncSystem()
        system.module_config = ModuleConfig(name="root")
        return system

    def _make_variable(self, name: str, value: float) -> Variable:
        return Variable(name, FloatValue(value))

    def test_runtime_reference_resolution_and_error_paths(self):
        root = self._make_system()
        root.variables["sample"] = self._make_variable("sample", 1.5)
        root.constants["SCALE"] = FloatValue(3.0)

        child = self._make_system()
        child.variables["level"] = self._make_variable("level", 7.0)
        child.input_variables["raw"] = self._make_variable("raw", 0.0)
        child.output_variables["level"] = child.variables["level"]

        root.imports = [
            ImportConfig(module="sensor.yaml", alias="sensor0", system=child)
        ]

        assert root._resolve_runtime_reference("sensor0.level").value == 7.0

        with pytest.raises(
            ValueError,
            match="Unknown runtime reference",
        ):
            root._resolve_runtime_reference("unknown.input_x")

        with pytest.raises(ValueError, match="Unknown runtime reference"):
            root._resolve_runtime_reference("missing.value")

        root.imports[0].system = None
        with pytest.raises(ValueError, match="Import 'sensor0' is not resolved"):
            root._resolve_runtime_reference("sensor0.level")

        root.imports[0].system = child
        child.variables.pop("level")
        with pytest.raises(ValueError, match="Unknown imported reference"):
            root._resolve_runtime_reference("sensor0.level")

    def test_expression_and_boolean_evaluation_covers_runtime_branches(self):
        system = self._make_system()
        x = self._make_variable("x", 6.0)
        y = self._make_variable("y", 2.0)
        system.variables.update({"x": x, "y": y})
        system.imports = []

        assert (
            system._evaluate_expression(ConstantExpression(FloatValue(4.0))).value
            == 4.0
        )
        assert system._evaluate_expression(VariableExpression(x)).value == 6.0
        assert (
            system._evaluate_expression(
                SumExpression(VariableExpression(x), VariableExpression(y))
            ).value
            == 8.0
        )
        assert (
            system._evaluate_expression(
                DifferenceExpression(VariableExpression(x), VariableExpression(y))
            ).value
            == 4.0
        )
        assert (
            system._evaluate_expression(
                MultiplicationExpression(VariableExpression(x), VariableExpression(y))
            ).value
            == 12.0
        )
        assert (
            system._evaluate_expression(
                DivisionExpression(VariableExpression(x), VariableExpression(y))
            ).value
            == 3.0
        )
        assert (
            system._evaluate_expression(
                UnaryMinusExpression(VariableExpression(y))
            ).value
            == -2.0
        )
        assert (
            system._evaluate_expression(
                IntMultiplicationExpression(3, VariableExpression(y))
            ).value
            == 6.0
        )
        assert (
            system._evaluate_expression(
                IntDivisionExpression(3, VariableExpression(x))
            ).value
            == 2.0
        )
        assert (
            system._evaluate_expression(
                FunctionCallExpression("sqrt", [ConstantExpression(FloatValue(9.0))])
            ).value
            == 3.0
        )

        with pytest.raises(ValueError, match="Unsupported expression node"):
            system._evaluate_expression(object())

        assert system._evaluate_boolean(BooleanConstantExpression(True)) is True
        assert (
            system._evaluate_boolean(
                BooleanAndExpression(
                    BooleanConstantExpression(True), BooleanConstantExpression(False)
                )
            )
            is False
        )
        assert (
            system._evaluate_boolean(
                BooleanOrExpression(
                    BooleanConstantExpression(True), BooleanConstantExpression(False)
                )
            )
            is True
        )
        assert (
            system._evaluate_boolean(
                BooleanNotExpression(BooleanConstantExpression(True))
            )
            is False
        )
        assert (
            system._evaluate_boolean(
                BooleanLessTestExpression(VariableExpression(y), VariableExpression(x))
            )
            is True
        )
        assert (
            system._evaluate_boolean(
                BooleanLessEqualTestExpression(
                    VariableExpression(y), VariableExpression(y)
                )
            )
            is True
        )
        assert (
            system._evaluate_boolean(
                BooleanGreaterTestExpression(
                    VariableExpression(x), VariableExpression(y)
                )
            )
            is True
        )
        assert (
            system._evaluate_boolean(
                BooleanGreaterEqualTestExpression(
                    VariableExpression(x), VariableExpression(x)
                )
            )
            is True
        )
        assert (
            system._evaluate_boolean(
                BooleanEqualTestExpression(VariableExpression(x), VariableExpression(x))
            )
            is True
        )
        assert (
            system._evaluate_boolean(
                BooleanNotEqualTestExpression(
                    VariableExpression(x), VariableExpression(y)
                )
            )
            is True
        )

        with pytest.raises(ValueError, match="Unsupported boolean node"):
            system._evaluate_boolean(object())

    def test_import_inputs_cover_every_connection_kind(self):
        root = self._make_system()
        root.variables["sample"] = self._make_variable("sample", 2.5)
        root.constants["SCALE"] = FloatValue(4.0)
        root.inputs = {}

        child = self._make_system()
        child.input_variables["raw"] = self._make_variable("raw", 0.0)
        child.input_variables["unset"] = self._make_variable("unset", 0.0)
        child.variables["level"] = self._make_variable("level", 1.0)
        child.output_variables["level"] = child.variables["level"]

        sensor = ImportConfig(module="sensor.yaml", alias="sensor0", system=child)
        helper = ImportConfig(module="helper.yaml", alias="helper0", system=child)
        sensor.connections = {"raw": "sample", "unset": None}
        helper.connections = {"raw": "sensor0.level", "unset": "SCALE"}
        root.imports = [sensor, helper]
        inputs = root._build_import_inputs(sensor)
        assert inputs["raw"] == 2.5
        assert inputs["unset"] == 0.0

        inputs = root._build_import_inputs(helper)
        assert inputs["raw"] == 1.0
        assert inputs["unset"] == 4.0

        helper.connections["raw"] = "3"
        inputs = root._build_import_inputs(helper)
        assert inputs["raw"] == 3.0

    def test_reference_validation_and_step_missing_input_paths(self):
        root = self._make_system()
        root.cells = [
            Cell(
                1,
                {
                    "x": self._make_variable("x", 0.0),
                    "y": self._make_variable("y", 0.0),
                },
            )
        ]
        root.variables.update(root.cells[0].contents)
        root.input_variables["x"] = root.variables["x"]
        root.output_variables["y"] = root.variables["y"]
        root.module_config.zero_reset_mode = False
        root.rules = [
            Rule(
                root.variables["y"],
                ConstantExpression(FloatValue(1.0)),
                BooleanConstantExpression(True),
            )
        ]

        with pytest.raises(
            ValueError, match="Input variable x is required but not provided"
        ):
            root.step({})

        assert root.get_variable("missing") is None
        assert root.get_variable("x") is root.variables["x"]

        assert root._validate_reference("x") is None
        with pytest.raises(ValueError, match="must target an imported module"):
            root._validate_reference("unknown.input_x")

        imported = self._make_system()
        imported.input_variables["raw"] = self._make_variable("raw", 0.0)
        imported.output_variables["level"] = self._make_variable("level", 0.0)
        root.imports = [
            ImportConfig(
                module="sensor.yaml",
                alias="sensor0",
                system=imported,
                connections={"raw": "x"},
            )
        ]

        assert root._validate_reference("sensor0.level") is None

        root.imports[0].system = None
        with pytest.raises(ValueError, match="Import 'sensor0' is not resolved"):
            root._validate_reference("sensor0.level")

        root.imports[0].system = imported
        with pytest.raises(
            ValueError, match="must target an imported module input or output"
        ):
            root._validate_reference("sensor0.missing")

        root.imports[0].connections = {"not_input": "x"}
        with pytest.raises(ValueError, match="is not an input on 'sensor0'"):
            root.validate_references()

        root.imports = [
            ImportConfig(module="sensor.yaml", alias="sensor0", system=None)
        ]
        root.validate_references()


IMPORTED_INPUT = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "verification"
    / "sva"
    / "imported_input"
)


def test_last_import_inputs_holds_the_given_values_as_a_copy():
    # The child consumes its input a; the system keeps what it was given.
    system = NncSystem.from_yaml(
        str(IMPORTED_INPUT / "parent.yaml"), import_paths=[str(IMPORTED_INPUT)]
    )
    assert system.last_import_inputs == {}
    system.step()
    system.step()

    given = system.last_import_inputs
    given["child0"]["a"] = 99.0
    given.clear()

    assert system.last_import_inputs == {"child0": {"a": 1.0}}


def test_imports_read_the_configuration_before_the_step():
    # c1 reads c0's output: it is given c0.y from before the step (numerical
    # P system semantics, as in the generated RTL), so c1.y lags c0.y by one.
    system = NncSystem.from_yaml(
        str(IMPORTED_INPUT / "chain.yaml"), import_paths=[str(IMPORTED_INPUT)]
    )
    rows = []
    for _ in range(4):
        system.step()
        children = {item.alias: item.system for item in system.imports}
        rows.append(
            (
                children["c0"].variables["y"].value.value,
                children["c1"].variables["y"].value.value,
            )
        )

    assert rows == [(0.0, 0.0), (1.0, 0.0), (2.0, 1.0), (3.0, 2.0)]


def test_imports_reading_each_other_need_no_ordering():
    # A cycle between imports is well defined when every import reads the
    # configuration before the step: each sees the other one step later.
    system = NncSystem.from_yaml(
        str(IMPORTED_INPUT / "loop.yaml"), import_paths=[str(IMPORTED_INPUT)]
    )
    system.step()
    system.step()

    assert system.last_import_inputs == {"c0": {"a": 1.0}, "c1": {"a": 1.0}}
