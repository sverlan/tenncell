"""Python expression emission for TENNCell AST nodes."""

from typing import Any

from ...parser.ast import *
from ...parser.ast.value import *


class PythonExpressionEmitter:
    """Emit Python expressions from TENNCell AST nodes."""

    def _reference_code(self, reference: str) -> str:
        if "." in reference:
            return f"self._ref('{reference}')"
        return f"self.{reference}"

    def _get_producer_variables(self, producer_expr) -> set:
        """Extract variable names used in a producer expression."""
        variables = set()

        if hasattr(producer_expr, "get_variables"):
            expr_vars = producer_expr.get_variables()
            variables.update(expr_vars.keys())

        return variables

    def visit(self, node) -> str:
        """Generic visit method that dispatches to specific visitor methods."""
        method_name = f"visit_{type(node).__name__}"
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node) -> str:
        """Default visitor for unknown node types."""
        return f"# Unknown node type: {type(node).__name__}"

    def visit_ConstantExpression(self, node: ConstantExpression) -> str:
        """Visit a constant expression."""
        return self.visit_value(node.value)

    def visit_VariableExpression(self, node: VariableExpression) -> str:
        """Visit a variable expression."""
        return f"self.{node.variable.name}"

    def visit_ReferenceExpression(self, node: ReferenceExpression) -> str:
        """Visit a qualified reference expression."""
        reference = ".".join(node.parts)
        ctx = getattr(self, "_emission_context", None)
        if ctx is not None and ctx.composed_mode:
            return self._reference_code(reference)
        return reference

    def visit_SumExpression(self, node: SumExpression) -> str:
        """Visit a sum expression."""
        left = self.visit(node.left)
        right = self.visit(node.right)
        return f"({left} + {right})"

    def visit_DifferenceExpression(self, node: DifferenceExpression) -> str:
        """Visit a difference expression."""
        left = self.visit(node.left)
        right = self.visit(node.right)
        return f"({left} - {right})"

    def visit_MultiplicationExpression(self, node: MultiplicationExpression) -> str:
        """Visit a multiplication expression."""
        left = self.visit(node.left)
        right = self.visit(node.right)
        return f"({left} * {right})"

    def visit_DivisionExpression(self, node: DivisionExpression) -> str:
        """Visit a division expression."""
        left = self.visit(node.left)
        right = self.visit(node.right)
        return f"({left} / {right})"

    def visit_UnaryMinusExpression(self, node: UnaryMinusExpression) -> str:
        """Visit a unary minus expression."""
        operand = self.visit(node.expression)
        return f"(-{operand})"

    def visit_IntMultiplicationExpression(
        self, node: IntMultiplicationExpression
    ) -> str:
        """Visit an integer multiplication expression."""
        operand = self.visit(node.expression)
        return f"({node.constant} * {operand})"

    def visit_IntDivisionExpression(self, node: IntDivisionExpression) -> str:
        """Visit an integer division expression."""
        operand = self.visit(node.expression)
        return f"({operand} / {node.constant})"

    def visit_FunctionCallExpression(self, node) -> str:
        """Visit a function call expression."""
        args = [self.visit(arg) for arg in node.arguments]
        args_str = ", ".join(args)

        function_mappings = {
            "sin": "math.sin",
            "cos": "math.cos",
            "tan": "math.tan",
            "exp": "math.exp",
            "log": "math.log",
            "sqrt": "math.sqrt",
            "pow": "math.pow",
            "abs": "abs",
            "floor": "math.floor",
            "ceil": "math.ceil",
            "pi": "math.pi",
            "e": "math.e",
        }

        python_function = function_mappings.get(node.function_name, node.function_name)

        if len(node.arguments) == 0:
            return python_function
        return f"{python_function}({args_str})"

    def visit_BooleanConstantExpression(self, node: BooleanConstantExpression) -> str:
        """Visit a boolean constant expression."""
        return "True" if node.value else "False"

    def visit_BooleanAndExpression(self, node: BooleanAndExpression) -> str:
        """Visit a boolean AND expression."""
        left = self.visit(node.left)
        right = self.visit(node.right)
        return f"({left} and {right})"

    def visit_BooleanOrExpression(self, node: BooleanOrExpression) -> str:
        """Visit a boolean OR expression."""
        left = self.visit(node.left)
        right = self.visit(node.right)
        return f"({left} or {right})"

    def visit_BooleanNotExpression(self, node: BooleanNotExpression) -> str:
        """Visit a boolean NOT expression."""
        operand = self.visit(node.expression)
        return f"(not {operand})"

    def visit_BooleanLessTestExpression(self, node: BooleanLessTestExpression) -> str:
        """Visit a boolean less than expression."""
        left = self.visit(node.left)
        right = self.visit(node.right)
        return f"({left} < {right})"

    def visit_BooleanLessEqualTestExpression(
        self, node: BooleanLessEqualTestExpression
    ) -> str:
        """Visit a boolean less than or equal expression."""
        left = self.visit(node.left)
        right = self.visit(node.right)
        return f"({left} <= {right})"

    def visit_BooleanGreaterTestExpression(
        self, node: BooleanGreaterTestExpression
    ) -> str:
        """Visit a boolean greater than expression."""
        left = self.visit(node.left)
        right = self.visit(node.right)
        return f"({left} > {right})"

    def visit_BooleanGreaterEqualTestExpression(
        self, node: BooleanGreaterEqualTestExpression
    ) -> str:
        """Visit a boolean greater than or equal expression."""
        left = self.visit(node.left)
        right = self.visit(node.right)
        return f"({left} >= {right})"

    def visit_BooleanEqualTestExpression(self, node: BooleanEqualTestExpression) -> str:
        """Visit a boolean equality expression."""
        left = self.visit(node.left)
        right = self.visit(node.right)
        return f"({left} == {right})"

    def visit_BooleanNotEqualTestExpression(
        self, node: BooleanNotEqualTestExpression
    ) -> str:
        """Visit a boolean not equal expression."""
        left = self.visit(node.left)
        right = self.visit(node.right)
        return f"({left} != {right})"

    def visit_value(self, value: Any) -> str:
        """Visit a value node and return Python representation."""
        if hasattr(value, "value"):
            if isinstance(value.value, (int, float)):
                return str(value.value)
            elif isinstance(value.value, list):
                return f"[{', '.join(str(v) for v in value.value)}]"
        return str(value)
