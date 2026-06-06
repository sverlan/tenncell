from lark import Lark, Transformer, GrammarError, Tree
from lark.exceptions import VisitError

from .ast.value import FloatValue
from .ast import *
from ..model.rule import Rule
from .ast.expression import FunctionCallExpression

expression_grammar = r"""
start: expr

?expr: term
      | expr "+" term  -> sum
      | expr "-" term  -> difference

?term: factor
     | term "*" factor  -> multiplication
     | term "/" factor  -> division

?factor: NUMBER       -> number
       | ref          -> variable
       | ID "(" [arg_list] ")"  -> function_call
       | "-" factor    -> unary_minus
       | "(" expr ")"

ref: ID ("." ID)* -> reference

arg_list: expr ("," expr)*  -> arguments


%import common.NUMBER
%import common.CNAME -> ID
%import common.WS
%ignore WS
"""

boolean_expression_grammar = (
    expression_grammar
    + r"""
?cond: and_cond
    | cond "||" cond  -> bor
    
?and_cond: atom
    | and_cond "&&" atom -> band

?atom: literal
    | "!" literal -> bnot


?literal: CONST -> constant
    | test
    | "(" cond ")"

CONST.2: "true"i | "false"i
    
?test: expr OP expr -> xtest

OP: ">=" | ">" | "==" | "<=" | "<" | "!="    
 
"""
)

rule_expression_grammar = (
    boolean_expression_grammar
    + r"""
?rule: (cond (":" | "|"))? expr "->" ref  -> rule
"""
)

variable_assignment_expression_grammar = (
    expression_grammar
    + r"""
?assignment: ID "=" expr ("," ID "=" expr)* -> assignment 
"""
)


_expression_parser = Lark(expression_grammar, parser="lalr", start="expr")
_condition_parser = Lark(boolean_expression_grammar, parser="lalr", start="cond")
_rule_parser = Lark(rule_expression_grammar, parser="lalr", start="rule")
_variable_assignment_parser = Lark(
    variable_assignment_expression_grammar, parser="lalr", start="assignment"
)


def _transform_tree(transformer: Transformer, tree: Tree):
    try:
        return transformer.transform(tree)
    except VisitError as error:
        raise error.orig_exc from None


# Create a custom transformer to build the expression tree
class ExpressionTransformer(Transformer):
    """Lower parsed arithmetic trees into TENNCell expression objects."""

    def __init__(
        self,
        context_variables: dict[str, Variable],
        constants: dict[str, FloatValue] | None = None,
        aliases: dict[str, Expression] | None = None,
    ):
        super().__init__()
        self.context_variables = context_variables
        self.constants = constants or {}
        self.aliases = aliases or {}

    def sum(self, args):
        return SumExpression(args[0], args[1])

    def difference(self, args):
        return DifferenceExpression(args[0], args[1])

    def multiplication(self, args):
        return MultiplicationExpression(args[0], args[1])

    def division(self, args):
        return DivisionExpression(args[0], args[1])

    def number(self, args):
        return ConstantExpression(FloatValue(args[0]))

    def reference(self, args):
        return [str(arg) for arg in args]

    def unary_minus(self, args):
        return UnaryMinusExpression(args[0])

    def variable(self, args):
        parts = args[0]
        name = parts[0]
        if len(parts) == 1:
            if name in self.aliases:
                return self.aliases[name]
            if name in self.constants:
                return ConstantExpression(self.constants[name])
            if name in self.context_variables:
                return VariableExpression(self.context_variables[name])
            raise GrammarError(f"Variable {name} not defined in the context")
        return ReferenceExpression(parts)

    def arguments(self, args):
        return args

    def function_call(self, args):
        function_name = str(args[0])
        arguments = args[1] if len(args) > 1 else []
        return FunctionCallExpression(function_name, arguments)


class ConditionTransformer(ExpressionTransformer):
    """Lower parsed boolean trees into TENNCell boolean expressions."""

    def constant(self, args):
        if str(args[0]).lower() == "true":
            return BooleanConstantExpression(True)
        else:
            return BooleanConstantExpression(False)

    def bnot(self, args):
        return BooleanNotExpression(args[0])

    def band(self, args):
        return BooleanAndExpression(args[0], args[1])

    def bor(self, args):
        return BooleanOrExpression(args[0], args[1])

    def xtest(self, args):
        left = args[0]
        op = args[1]
        right = args[2]

        match op:
            case "<=":
                return BooleanLessEqualTestExpression(left, right)
            case "<":
                return BooleanLessTestExpression(left, right)
            case "==":
                return BooleanEqualTestExpression(left, right)
            case "!=":
                return BooleanNotEqualTestExpression(left, right)
            case ">=":
                return BooleanGreaterEqualTestExpression(left, right)
            case ">":
                return BooleanGreaterTestExpression(left, right)
            case _:  # pragma: no cover
                raise GrammarError(f"Operator {op} not defined")


class RuleTransformer(ConditionTransformer):
    """Lower rule syntax into model :class:`Rule` instances."""

    def rule(self, args):
        if len(args) == 3:
            guard = args[0]
            producer = args[1]
            consumer_ref = args[2]
        else:
            guard = BooleanConstantExpression(True)
            producer = args[0]
            consumer_ref = args[1]

        if len(consumer_ref) != 1:
            raise GrammarError(
                f"Rule consumer {'.'.join(consumer_ref)} must be a local variable"
            )

        consumer_str = consumer_ref[0]
        if consumer_str not in self.context_variables:
            raise GrammarError(f"Variable {consumer_str} not defined in the context")
        return Rule(
            guard=guard,
            producer=producer,
            consumer=self.context_variables[consumer_str],
        )


class AssignmentTransformer(ExpressionTransformer):
    """Lower assignment syntax into the variable map used by the model."""

    def assignment(self, args):
        variables = {}
        nb = len(args)
        for i in range(0, nb, 2):
            variable_name = str(args[i])
            expr = args[i + 1]

            # Check if the expression only references already defined variables
            for var_name in expr.get_variables():
                if var_name not in self.context_variables:
                    raise GrammarError(
                        f"Variable {var_name} used in assignment is not defined"
                    )

            # Evaluate the expression to get its value
            result_value = expr.evaluate()

            # Store the variable
            if variable_name not in self.context_variables:
                variable = Variable(variable_name, result_value)
            else:
                variable = self.context_variables[variable_name]
                variable.value = result_value

            variables[variable_name] = variable
        return variables


# Parse the expression and build the expression tree
def parse_expression(
    expression_string: str,
    context_variables: dict[str, Variable],
    constants: dict[str, FloatValue] | None = None,
    aliases: dict[str, Expression] | None = None,
) -> Expression | Tree:
    """Parse a TENNCell arithmetic expression into the AST used by the model.

    Args:
        expression_string: Expression source text.
        context_variables: Variables available in the current scope.
        constants: Optional constant map used during parsing.
        aliases: Optional alias map used during parsing.

    Returns:
        The lowered arithmetic expression tree.

    Raises:
        GrammarError: If the expression is invalid or references an unknown
            variable.
    """
    tree = _expression_parser.parse(expression_string)
    return _transform_tree(
        ExpressionTransformer(context_variables, constants, aliases), tree
    )


# Parse the condition and build the expression tree
def parse_condition(
    condition_string: str,
    context_variables: dict[str, Variable],
    constants: dict[str, FloatValue] | None = None,
    aliases: dict[str, Expression] | None = None,
) -> BooleanExpression | Tree:
    """Parse a TENNCell boolean condition into the AST used by rules and guards.

    Args:
        condition_string: Condition source text.
        context_variables: Variables available in the current scope.
        constants: Optional constant map used during parsing.
        aliases: Optional alias map used during parsing.

    Returns:
        The lowered boolean expression tree.

    Raises:
        GrammarError: If the condition is invalid or references an unknown
            variable.
    """
    tree = _condition_parser.parse(condition_string)
    return _transform_tree(
        ConditionTransformer(context_variables, constants, aliases), tree
    )


# Parse the rule and build the expression tree
def parse_rule(
    rule_string: str,
    context_variables: dict[str, Variable],
    constants: dict[str, FloatValue] | None = None,
    aliases: dict[str, Expression] | None = None,
) -> Rule | Tree:
    """Parse a TENNCell rule string into a lowered :class:`Rule` object.

    Args:
        rule_string: Rule source text.
        context_variables: Variables available in the current scope.
        constants: Optional constant map used during parsing.
        aliases: Optional alias map used during parsing.

    Returns:
        The lowered rule object.

    Raises:
        GrammarError: If the rule is invalid or references an unknown
            variable.
    """
    tree = _rule_parser.parse(rule_string)
    return _transform_tree(RuleTransformer(context_variables, constants, aliases), tree)


# Parse the rule and build the expression tree
def parse_variable_assignment(
    assignment_string: str,
    context_variables: dict[str, Variable],
    constants: dict[str, FloatValue] | None = None,
    aliases: dict[str, Expression] | None = None,
) -> dict[str, Variable] | Tree:
    """Parse one or more variable assignments into the model variable map.

    Args:
        assignment_string: Assignment source text.
        context_variables: Variables available in the current scope.
        constants: Optional constant map used during parsing.
        aliases: Optional alias map used during parsing.

    Returns:
        The updated variable mapping produced by the assignment.

    Raises:
        GrammarError: If the assignment is invalid or references an unknown
            variable.
    """
    tree = _variable_assignment_parser.parse(assignment_string)
    return _transform_tree(
        AssignmentTransformer(context_variables, constants, aliases), tree
    )
