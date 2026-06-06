import pytest
import math
from nnc.parser.ast.value import FloatValue
from nnc.parser.ast import *


class TestExpression:
    def test_variable(self):
        var = Variable("x", FloatValue(1.23))
        assert var.name == "x"
        assert var.value.value == 1.23

    def test_variable_str(self):
        var = Variable("x", FloatValue(1.23))
        assert str(var) == "x"

    def test_variable_repr(self):
        var = Variable("x", FloatValue(1.23))
        assert repr(var) == "Variable(x,FloatValue(1.23))"

    def test_constant_expression(self):
        ce = ConstantExpression(FloatValue(1.23))
        assert ce.value.value == 1.23
        assert ce.evaluate().value == 1.23
        assert ce.get_variables() == {}
        assert str(ce) == "1.23"
        assert repr(ce) == "ConstantExpression(FloatValue(1.23))"

    def test_variable_expression(self):
        ve = VariableExpression(Variable("x", FloatValue(1.23)))
        assert ve.variable.name == "x"
        assert ve.variable.value.value == 1.23
        assert ve.evaluate().value == 1.23
        assert ve.get_variables() == {"x": ve.variable}
        assert str(ve) == "x"
        assert repr(ve) == "VariableExpression(Variable(x,FloatValue(1.23)))"

    def test_binary_expression(self):
        be = SumExpression(
            VariableExpression(Variable("x", FloatValue(1.23))),
            VariableExpression(Variable("y", FloatValue(4.56))),
        )
        assert be.left.variable.name == "x"
        assert be.left.variable.value.value == 1.23
        assert be.right.variable.name == "y"
        assert be.right.variable.value.value == 4.56
        assert math.isclose(be.evaluate().value, 5.79)
        assert be.get_variables() == {"x": be.left.variable, "y": be.right.variable}
        assert str(be) == "(x + y)"
        assert (
            repr(be)
            == "BinaryExpression(VariableExpression(Variable(x,FloatValue(1.23))),VariableExpression(Variable(y,FloatValue(4.56))),'+')"
        )

    def test_unary_expression(self):
        ue = UnaryMinusExpression(VariableExpression(Variable("x", FloatValue(1.23))))
        assert ue.expression.variable.name == "x"
        assert ue.expression.variable.value.value == 1.23
        assert ue.evaluate().value == -1.23
        assert ue.get_variables() == {"x": ue.expression.variable}
        assert str(ue) == "-(x)"
        assert (
            repr(ue)
            == "UnaryMinusExpression(VariableExpression(Variable(x,FloatValue(1.23))))"
        )

    def test_difference_expression(self):
        de = DifferenceExpression(
            VariableExpression(Variable("x", FloatValue(1.23))),
            VariableExpression(Variable("y", FloatValue(4.56))),
        )
        assert de.left.variable.name == "x"
        assert de.left.variable.value.value == 1.23
        assert de.right.variable.name == "y"
        assert de.right.variable.value.value == 4.56
        assert math.isclose(de.evaluate().value, -3.33)
        assert de.get_variables() == {"x": de.left.variable, "y": de.right.variable}
        assert str(de) == "(x - y)"
        assert (
            repr(de)
            == "BinaryExpression(VariableExpression(Variable(x,FloatValue(1.23))),VariableExpression(Variable(y,FloatValue(4.56))),'-')"
        )

    def test_division_expression(self):
        de = DivisionExpression(
            VariableExpression(Variable("x", FloatValue(1.23))),
            VariableExpression(Variable("y", FloatValue(4.56))),
        )
        assert de.left.variable.name == "x"
        assert de.left.variable.value.value == 1.23
        assert de.right.variable.name == "y"
        assert de.right.variable.value.value == 4.56
        assert math.isclose(de.evaluate().value, 0.26973684210526316)
        assert de.get_variables() == {"x": de.left.variable, "y": de.right.variable}
        assert str(de) == "(x / y)"
        assert (
            repr(de)
            == "BinaryExpression(VariableExpression(Variable(x,FloatValue(1.23))),VariableExpression(Variable(y,FloatValue(4.56))),'/')"
        )

    def test_int_multiplication_expression(self):
        de = IntMultiplicationExpression(
            2,
            VariableExpression(Variable("y", FloatValue(4))),
        )

        assert de.constant == 2
        assert de.expression.variable.name == "y"
        assert de.expression.variable.value.value == 4
        assert math.isclose(de.evaluate().value, 8)
        assert de.get_variables() == {"y": de.expression.variable}
        assert str(de) == "(2 * y)"
        assert (
            repr(de)
            == "IntMultiplicationExpression(2,VariableExpression(Variable(y,FloatValue(4.0))))"
        )

    def test_int_division_expression(self):
        de = IntDivisionExpression(
            3,
            VariableExpression(Variable("y", FloatValue(6.0))),
        )
        assert de.constant == 3
        assert de.expression.variable.name == "y"
        assert de.expression.variable.value.value == 6.0
        assert math.isclose(de.evaluate().value, 2.0)
        assert de.get_variables() == {"y": de.expression.variable}
        assert str(de) == "(y / 3)"
        assert (
            repr(de)
            == "IntDivisionExpression(3,VariableExpression(Variable(y,FloatValue(6.0))))"
        )

    def test_nested_expression(self):
        ne = SumExpression(
            VariableExpression(Variable("x", FloatValue(1.23))),
            UnaryMinusExpression(VariableExpression(Variable("y", FloatValue(4.56)))),
        )
        assert ne.left.variable.name == "x"
        assert ne.left.variable.value.value == 1.23
        assert ne.right.expression.variable.name == "y"
        assert ne.right.expression.variable.value.value == 4.56
        assert math.isclose(ne.evaluate().value, -3.33)
        assert ne.get_variables() == {
            "x": ne.left.variable,
            "y": ne.right.expression.variable,
        }
        assert str(ne) == "(x + -(y))"
        assert (
            repr(ne)
            == "BinaryExpression(VariableExpression(Variable(x,FloatValue(1.23))),UnaryMinusExpression(VariableExpression(Variable(y,FloatValue(4.56)))),'+')"
        )

    def test_nested_expression2(self):
        ne = SumExpression(
            UnaryMinusExpression(VariableExpression(Variable("x", FloatValue(1.23)))),
            VariableExpression(Variable("y", FloatValue(4.56))),
        )
        assert ne.left.expression.variable.name == "x"
        assert ne.left.expression.variable.value.value == 1.23
        assert ne.right.variable.name == "y"
        assert ne.right.variable.value.value == 4.56
        assert math.isclose(ne.evaluate().value, 3.33)
        assert ne.get_variables() == {
            "x": ne.left.expression.variable,
            "y": ne.right.variable,
        }
        assert str(ne) == "(-(x) + y)"
        assert (
            repr(ne)
            == "BinaryExpression(UnaryMinusExpression(VariableExpression(Variable(x,FloatValue(1.23)))),VariableExpression(Variable(y,FloatValue(4.56))),'+')"
        )

    def test_nested_expression3(self):
        ne = SumExpression(
            UnaryMinusExpression(VariableExpression(Variable("x", FloatValue(1.23)))),
            UnaryMinusExpression(VariableExpression(Variable("y", FloatValue(4.56)))),
        )
        assert ne.left.expression.variable.name == "x"
        assert ne.left.expression.variable.value.value == 1.23
        assert ne.right.expression.variable.name == "y"
        assert ne.right.expression.variable.value.value == 4.56
        assert math.isclose(ne.evaluate().value, -5.79)
        assert ne.get_variables() == {
            "x": ne.left.expression.variable,
            "y": ne.right.expression.variable,
        }
        assert str(ne) == "(-(x) + -(y))"
        assert (
            repr(ne)
            == "BinaryExpression(UnaryMinusExpression(VariableExpression(Variable(x,FloatValue(1.23)))),UnaryMinusExpression(VariableExpression(Variable(y,FloatValue(4.56)))),'+')"
        )


if __name__ == "__main__":
    pytest.main()  # pragma: no cover
