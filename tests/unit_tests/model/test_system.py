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

    @pytest.mark.parametrize("zero_reset_mode", [False, True])
    def test_add_rule_rejects_input_destination_without_appending(self, zero_reset_mode):
        """The public model API enforces read-only input destinations."""
        system = NncSystem()
        system.module_config.zero_reset_mode = zero_reset_mode
        sensor = Variable("sensor", 0)
        system.variables["sensor"] = sensor
        system.input_variables["sensor"] = sensor
        rule = Rule(sensor, VariableExpression(sensor), BooleanConstantExpression(True))

        with pytest.raises(ValueError, match="destination 'sensor' is an input"):
            system.add_rule(rule)

        assert system.rules == []

    def test_add_rule_accepts_an_input_as_a_source(self):
        """An input can produce a value for a writable local variable."""
        system = NncSystem()
        sensor = Variable("sensor", 0)
        output = Variable("output", 0)
        system.variables.update(sensor=sensor, output=output)
        system.input_variables["sensor"] = sensor
        rule = Rule(output, VariableExpression(sensor), BooleanConstantExpression(True))

        system.add_rule(rule)

        assert system.rules == [rule]


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
