from nnc.parser.ast.value import FloatValue
from nnc.parser.ast.boolean_expression import *
from nnc.parser.ast.expression import *


class TestBooleanExpression:
    def test_boolean_constant_expression(self):
        bce = BooleanConstantExpression(True)
        assert bce.value == True
        assert bce.evaluate() == True
        assert str(bce) == "True"
        assert repr(bce) == "BooleanConstantExpression(True)"

    def test_boolean_greater_test_expression(self):
        bgte = BooleanGreaterTestExpression(
            VariableExpression(Variable("x", FloatValue(1.23))),
            VariableExpression(Variable("y", FloatValue(4.56))),
        )
        assert bgte.left.variable.name == "x"
        assert bgte.left.variable.value.value == 1.23
        assert bgte.right.variable.name == "y"
        assert bgte.right.variable.value.value == 4.56
        assert bgte.evaluate() == False
        assert bgte.get_variables() == {
            "x": bgte.left.variable,
            "y": bgte.right.variable,
        }
        assert str(bgte) == "(x > y)"
        assert (
            repr(bgte)
            == "BooleanTestExpression('>',VariableExpression(Variable(x,FloatValue(1.23))),VariableExpression(Variable(y,FloatValue(4.56))))"
        )

    def test_boolean_greater_equal_test_expression(self):
        bgete = BooleanGreaterEqualTestExpression(
            VariableExpression(Variable("x", FloatValue(1.23))),
            VariableExpression(Variable("y", FloatValue(4.56))),
        )
        assert bgete.left.variable.name == "x"
        assert bgete.left.variable.value.value == 1.23
        assert bgete.right.variable.name == "y"
        assert bgete.right.variable.value.value == 4.56
        assert bgete.evaluate() == False
        assert bgete.get_variables() == {
            "x": bgete.left.variable,
            "y": bgete.right.variable,
        }
        assert str(bgete) == "(x >= y)"
        assert (
            repr(bgete)
            == "BooleanTestExpression('>=',VariableExpression(Variable(x,FloatValue(1.23))),VariableExpression(Variable(y,FloatValue(4.56))))"
        )

    def test_boolean_less_test_expression(self):
        blte = BooleanLessTestExpression(
            VariableExpression(Variable("x", FloatValue(1.23))),
            VariableExpression(Variable("y", FloatValue(4.56))),
        )
        assert blte.left.variable.name == "x"
        assert blte.left.variable.value.value == 1.23
        assert blte.right.variable.name == "y"
        assert blte.right.variable.value.value == 4.56
        assert blte.evaluate() == True
        assert blte.get_variables() == {
            "x": blte.left.variable,
            "y": blte.right.variable,
        }
        assert str(blte) == "(x < y)"
        assert (
            repr(blte)
            == "BooleanTestExpression('<',VariableExpression(Variable(x,FloatValue(1.23))),VariableExpression(Variable(y,FloatValue(4.56))))"
        )

    def test_boolean_less_equal_test_expression(self):
        blete = BooleanLessEqualTestExpression(
            VariableExpression(Variable("x", FloatValue(1.23))),
            VariableExpression(Variable("y", FloatValue(4.56))),
        )
        assert blete.left.variable.name == "x"
        assert blete.left.variable.value.value == 1.23
        assert blete.right.variable.name == "y"
        assert blete.right.variable.value.value == 4.56
        assert blete.evaluate() == True
        assert blete.get_variables() == {
            "x": blete.left.variable,
            "y": blete.right.variable,
        }
        assert str(blete) == "(x <= y)"
        assert (
            repr(blete)
            == "BooleanTestExpression('<=',VariableExpression(Variable(x,FloatValue(1.23))),VariableExpression(Variable(y,FloatValue(4.56))))"
        )

    def test_boolean_equal_test_expression(self):
        bete = BooleanEqualTestExpression(
            VariableExpression(Variable("x", FloatValue(1.23))),
            VariableExpression(Variable("y", FloatValue(4.56))),
        )
        assert bete.left.variable.name == "x"
        assert bete.left.variable.value.value == 1.23
        assert bete.right.variable.name == "y"
        assert bete.right.variable.value.value == 4.56
        assert bete.evaluate() == False
        assert bete.get_variables() == {
            "x": bete.left.variable,
            "y": bete.right.variable,
        }
        assert str(bete) == "(x == y)"
        assert (
            repr(bete)
            == "BooleanTestExpression('==',VariableExpression(Variable(x,FloatValue(1.23))),VariableExpression(Variable(y,FloatValue(4.56))))"
        )

    def test_boolean_not_equal_test_expression(self):
        bnete = BooleanNotEqualTestExpression(
            VariableExpression(Variable("x", FloatValue(1.23))),
            VariableExpression(Variable("y", FloatValue(4.56))),
        )
        assert bnete.left.variable.name == "x"
        assert bnete.left.variable.value.value == 1.23
        assert bnete.right.variable.name == "y"
        assert bnete.right.variable.value.value == 4.56
        assert bnete.evaluate() == True
        assert bnete.get_variables() == {
            "x": bnete.left.variable,
            "y": bnete.right.variable,
        }
        assert str(bnete) == "(x != y)"
        assert (
            repr(bnete)
            == "BooleanTestExpression('!=',VariableExpression(Variable(x,FloatValue(1.23))),VariableExpression(Variable(y,FloatValue(4.56))))"
        )

    def test_boolean_and_expression(self):
        bae = BooleanAndExpression(
            BooleanConstantExpression(True),
            BooleanConstantExpression(False),
        )
        assert bae.left.value == True
        assert bae.right.value == False
        assert bae.evaluate() == False
        assert bae.get_variables() == {}
        assert str(bae) == "(True && False)"
        assert (
            repr(bae)
            == "BooleanBinaryExpression('&&',BooleanConstantExpression(True),BooleanConstantExpression(False))"
        )

    def test_boolean_or_expression(self):
        boe = BooleanOrExpression(
            BooleanConstantExpression(True),
            BooleanConstantExpression(False),
        )
        assert boe.left.value == True
        assert boe.right.value == False
        assert boe.evaluate() == True
        assert boe.get_variables() == {}
        assert str(boe) == "(True || False)"
        assert (
            repr(boe)
            == "BooleanBinaryExpression('||',BooleanConstantExpression(True),BooleanConstantExpression(False))"
        )

    def test_boolean_not_expression(self):
        bne = BooleanNotExpression(
            BooleanConstantExpression(True),
        )
        assert bne.expression.value == True
        assert bne.evaluate() == False
        assert bne.get_variables() == {}
        assert str(bne) == "!(True)"
        assert repr(bne) == "BooleanNotExpression(BooleanConstantExpression(True))"


if __name__ == "__main__":
    pytest.main()  # pragma: no cover
