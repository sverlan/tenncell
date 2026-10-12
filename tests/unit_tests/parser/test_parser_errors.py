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


def test_a_grammar_rule_without_transformer_callback_is_an_error():
    # lark hands back the tree itself for such a rule; the parser must not
    # return it as if it were an AST node.
    from lark import Transformer, Tree

    from nnc.parser.ast import Expression
    from nnc.parser.parser import _transform_tree

    with pytest.raises(ValueError, match="parsing produced Tree, expected Expression"):
        _transform_tree(Transformer(), Tree("orphan", []), Expression)


def test_a_result_of_the_wrong_kind_is_an_error():
    from lark import Transformer, Tree

    from nnc.parser.ast import Expression
    from nnc.parser.parser import _transform_tree

    class Wrong(Transformer):
        def orphan(self, children):
            return 42

    with pytest.raises(ValueError, match="parsing produced int, expected Expression"):
        _transform_tree(Wrong(), Tree("orphan", []), Expression)
