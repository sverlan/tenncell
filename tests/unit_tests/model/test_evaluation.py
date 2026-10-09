"""Contract tests for the shared expression evaluator."""

import struct

import pytest

from nnc.model.evaluation import evaluate_boolean, evaluate_expression
from nnc.parser import parse_condition, parse_expression
from nnc.parser.ast import Variable, VariableExpression
from nnc.parser.ast.value import FloatValue
from nnc.parser.ast.value.math_functions import MathFunctions


class _Context:
    """Evaluation context reading a plain mapping and logging function calls."""

    def __init__(self, values: dict[str, float]):
        self.values = values
        self.calls: list[str] = []

    def variable_value(self, node: VariableExpression) -> FloatValue:
        return FloatValue(self.values[node.variable.name])

    def reference_value(self, reference: str) -> FloatValue:
        return FloatValue(self.values[reference])

    def call_function(self, name: str, arguments: list[float]) -> FloatValue:
        self.calls.append(name)
        return FloatValue(MathFunctions.evaluate(name, arguments))


def _variables(values: dict[str, float]) -> dict[str, Variable]:
    return {name: Variable(name, FloatValue(value)) for name, value in values.items()}


def _bits(value: float) -> bytes:
    return struct.pack("<d", float(value))


@pytest.mark.parametrize(
    "text",
    [
        "x + y * 2 - z / 3",
        "-(x - y) * 0.1 + 0.2",
        "sqrt(abs(x - y)) + max(x, y, z) / min(y, 0.5)",
        "pow(x, 2) + atan2(y, z) - floor(z * 3.7)",
        "x * 3 / 7",
    ],
)
def test_bound_variables_and_row_values_give_identical_results(text):
    values = {"x": 0.1, "y": 0.2, "z": 0.055}
    variables = _variables(values)
    expression = parse_expression(text, variables, {}, {})

    class _BoundContext(_Context):
        def variable_value(self, node):
            return node.variable.value

    bound = evaluate_expression(expression, _BoundContext({}))
    row = evaluate_expression(expression, _Context(values))

    assert _bits(bound.value) == _bits(row.value)


def test_functions_are_called_left_to_right():
    variables = _variables({"x": 2.0})
    expression = parse_expression("sqrt(x) + abs(x) * floor(x)", variables, {}, {})
    context = _Context({"x": 2.0})

    evaluate_expression(expression, context)

    assert context.calls == ["sqrt", "abs", "floor"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("x > 0 || 1 / y > 0", True),  # right side would divide by zero
        ("x < 0 && 1 / y > 0", False),
    ],
)
def test_and_or_short_circuit(text, expected):
    variables = _variables({"x": 1.0, "y": 0.0})
    condition = parse_condition(text, variables, {}, {})

    assert evaluate_boolean(condition, _Context({"x": 1.0, "y": 0.0})) is expected


def test_right_operand_is_evaluated_when_needed():
    variables = _variables({"x": 1.0, "y": 0.0})
    condition = parse_condition("x > 0 && 1 / y > 0", variables, {}, {})

    with pytest.raises(ZeroDivisionError):
        evaluate_boolean(condition, _Context({"x": 1.0, "y": 0.0}))


def test_unsupported_nodes_are_rejected():
    with pytest.raises(ValueError, match="Unsupported expression node"):
        evaluate_expression(object(), _Context({}))
    with pytest.raises(ValueError, match="Unsupported boolean node"):
        evaluate_boolean(object(), _Context({}))
