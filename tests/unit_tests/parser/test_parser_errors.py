"""Parser error contract tests."""

import pytest
from lark import GrammarError

from nnc.parser import parse_expression, parse_rule
from nnc.parser.parser import AssignmentTransformer
from nnc.parser.ast import Variable
from nnc.parser.ast.value import FloatValue


class TestParserErrors:
    def test_parse_expression_unknown_variable_raises(self):
        with pytest.raises(GrammarError, match="Variable x not defined in the context"):
            parse_expression("x + 1", {})

    def test_parse_rule_unknown_consumer_raises(self):
        context_variables = {"x": Variable("x", FloatValue(1.0))}

        with pytest.raises(GrammarError, match="Variable y not defined in the context"):
            parse_rule("x -> y", context_variables)

    def test_parse_rule_dotted_consumer_raises(self):
        context_variables = {"x": Variable("x", FloatValue(1.0))}

        with pytest.raises(
            GrammarError, match="Rule consumer y.z must be a local variable"
        ):
            parse_rule("x -> y.z", context_variables)

    def test_assignment_transformer_unknown_reference_raises(self):
        class FakeExpression:
            def get_variables(self):
                return {"x": Variable("x", FloatValue(1.0))}

            def evaluate(self):
                return FloatValue(1.0)

        transformer = AssignmentTransformer({})

        with pytest.raises(
            GrammarError, match="Variable x used in assignment is not defined"
        ):
            transformer.assignment(["y", FakeExpression()])
