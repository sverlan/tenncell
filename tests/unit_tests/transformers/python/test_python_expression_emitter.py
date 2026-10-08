"""Internal contract tests for Python expression emission helpers."""

from types import SimpleNamespace

from nnc.model.system import NncSystem
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
    IntDivisionExpression,
    IntMultiplicationExpression,
    ReferenceExpression,
    SumExpression,
    UnaryMinusExpression,
    Variable,
    VariableExpression,
)
from nnc.parser.ast.expression import FunctionCallExpression
from nnc.parser.ast.value import FloatValue
from nnc.transformers.python.emission_context import PythonEmissionContext
from nnc.transformers.python_transformer import PythonTransformer


class TestPythonExpressionEmitter:
    def test_reference_code_variants(self):
        emitter = PythonTransformer()

        assert emitter._reference_code("value") == "self.value"
        assert emitter._reference_code("sensor0.level") == "self._ref('sensor0.level')"

    def test_get_producer_variables_handles_presence_and_absence(self):
        emitter = PythonTransformer()

        class Producer:
            def get_variables(self):
                return {"x": Variable("x", FloatValue(1.0))}

        assert emitter._get_producer_variables(Producer()) == {"x"}
        assert emitter._get_producer_variables(object()) == set()

    def test_visit_value_supports_lists(self):
        emitter = PythonTransformer()

        assert emitter.visit_value(SimpleNamespace(value=[1, 2, 3])) == "[1, 2, 3]"

    def test_visit_reference_expression_depends_on_composed_mode(self):
        emitter = PythonTransformer()
        expr = ReferenceExpression(["sensor0", "level"])

        assert emitter.visit_ReferenceExpression(expr) == "sensor0.level"
        emitter._emission_context = PythonEmissionContext(
            system=NncSystem(), composed_mode=True
        )
        assert emitter.visit_ReferenceExpression(expr) == "self._ref('sensor0.level')"

    def test_visit_function_call_expression_handles_zero_and_nonzero_arity(self):
        emitter = PythonTransformer()

        assert (
            emitter.visit_FunctionCallExpression(FunctionCallExpression("pi", []))
            == "math.pi"
        )
        assert (
            emitter.visit_FunctionCallExpression(
                FunctionCallExpression(
                    "pow",
                    [
                        ConstantExpression(FloatValue(2.0)),
                        ConstantExpression(FloatValue(3.0)),
                    ],
                )
            )
            == "math.pow(2.0, 3.0)"
        )

    def test_visit_boolean_and_arithmetic_nodes(self):
        emitter = PythonTransformer()
        x = VariableExpression(Variable("x", FloatValue(1.0)))
        y = VariableExpression(Variable("y", FloatValue(2.0)))

        assert emitter.visit_SumExpression(SumExpression(x, y)) == "(self.x + self.y)"
        assert (
            emitter.visit_UnaryMinusExpression(UnaryMinusExpression(x)) == "(-self.x)"
        )
        assert (
            emitter.visit_IntMultiplicationExpression(IntMultiplicationExpression(3, x))
            == "(3 * self.x)"
        )
        assert (
            emitter.visit_IntDivisionExpression(IntDivisionExpression(3, y))
            == "(self.y / 3)"
        )
        assert (
            emitter.visit_BooleanConstantExpression(BooleanConstantExpression(True))
            == "True"
        )
        assert (
            emitter.visit_BooleanAndExpression(
                BooleanAndExpression(
                    BooleanConstantExpression(True), BooleanConstantExpression(False)
                )
            )
            == "(True and False)"
        )
        assert (
            emitter.visit_BooleanOrExpression(
                BooleanOrExpression(
                    BooleanConstantExpression(True), BooleanConstantExpression(False)
                )
            )
            == "(True or False)"
        )
        assert (
            emitter.visit_BooleanNotExpression(
                BooleanNotExpression(BooleanConstantExpression(True))
            )
            == "(not True)"
        )
        assert (
            emitter.visit_BooleanLessTestExpression(BooleanLessTestExpression(x, y))
            == "(self.x < self.y)"
        )
        assert (
            emitter.visit_BooleanLessEqualTestExpression(
                BooleanLessEqualTestExpression(x, y)
            )
            == "(self.x <= self.y)"
        )
        assert (
            emitter.visit_BooleanGreaterTestExpression(
                BooleanGreaterTestExpression(x, y)
            )
            == "(self.x > self.y)"
        )
        assert (
            emitter.visit_BooleanGreaterEqualTestExpression(
                BooleanGreaterEqualTestExpression(x, y)
            )
            == "(self.x >= self.y)"
        )
        assert (
            emitter.visit_BooleanEqualTestExpression(BooleanEqualTestExpression(x, y))
            == "(self.x == self.y)"
        )
        assert (
            emitter.visit_BooleanNotEqualTestExpression(
                BooleanNotEqualTestExpression(x, y)
            )
            == "(self.x != self.y)"
        )
