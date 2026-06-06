import pytest
from nnc import NncSystem
from nnc import Rule
from nnc.parser.ast import Variable, VariableExpression, BooleanConstantExpression
from nnc.parser.ast import SumExpression


class TestSystem:
    """Contract tests for the public system model surface."""

    def test_empty_system(self):
        system = NncSystem()
        assert system.rules == []


class TestRule:
    """Contract tests for the public rule model surface."""

    def test_rule_repr_and_string(self):
        x = Variable("x", 1)
        y = Variable("y", 2)
        rule = Rule(
            x,
            SumExpression(VariableExpression(x), VariableExpression(y)),
            BooleanConstantExpression(True),
        )
        assert rule.guard.__str__() == "True"
        assert rule.producer.__str__() == "(x + y)"
        assert rule.consumer.__str__() == "x"
        assert rule.vars == {"x": x, "y": y}
        assert rule.__str__() == "True : (x + y) -> x"
        assert rule.__repr__() == "True : (x + y) -> x"


if __name__ == "__main__":
    pytest.main()  # pragma: no cover
