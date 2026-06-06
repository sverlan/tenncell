from abc import abstractmethod, ABC
from typing import Any

from .value.numerical_value import NumericalValue
from .variable import Variable


class Expression(ABC):
    @abstractmethod
    def evaluate(self) -> Any:
        pass  # pragma: no cover

    @abstractmethod
    def get_variables(self) -> dict[str, Variable]:
        pass  # pragma: no cover


class ConstantExpression(Expression):
    value: NumericalValue

    def __init__(self, value: NumericalValue):
        self.value = value

    def evaluate(self) -> Any:
        return self.value

    def get_variables(self) -> dict[str, Variable]:
        return {}

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return f"ConstantExpression({self.value.__repr__()})"


class VariableExpression(Expression):
    def __init__(self, variable: Variable):
        self.variable = variable

    def evaluate(self) -> Any:
        return self.variable.value

    def get_variables(self) -> dict[str, Variable]:
        return {self.variable.name: self.variable}

    def __str__(self):
        return self.variable.name

    def __repr__(self):
        return f"VariableExpression({self.variable.__repr__()})"


class ReferenceExpression(Expression):
    """Reference to a qualified imported or external signal."""

    def __init__(self, parts: list[str]):
        self.parts = parts

    def evaluate(self) -> Any:
        raise ValueError(
            f"Cannot evaluate external reference {self}"
        )  # pragma: no cover

    def get_variables(self) -> dict[str, Variable]:
        return {}

    def __str__(self):
        return ".".join(self.parts)

    def __repr__(self):
        return f"ReferenceExpression({'.'.join(self.parts)})"


class BinaryExpression(Expression, ABC):
    def __init__(self, left: Expression, right: Expression, op: str = ""):
        self.left = left
        self.right = right
        self.op = op

    def get_variables(self) -> dict[str, Variable]:
        variables = self.left.get_variables()
        variables.update(self.right.get_variables())
        return variables

    def __str__(self):
        ll = self.left.__str__()
        r = self.right.__str__()
        return f"({ll} {self.op} {r})"

    def __repr__(self):
        ll = self.left.__repr__()
        r = self.right.__repr__()
        return f"BinaryExpression({ll},{r},'{self.op}')"


class SumExpression(BinaryExpression):
    def __init__(self, left: Expression, right: Expression):
        super().__init__(left, right, "+")

    def evaluate(self) -> Any:
        x = self.left.evaluate() + self.right.evaluate()
        return x


class DifferenceExpression(BinaryExpression):
    def __init__(self, left: Expression, right: Expression):
        super().__init__(left, right, "-")

    def evaluate(self) -> Any:
        return self.left.evaluate() - self.right.evaluate()


class MultiplicationExpression(BinaryExpression):
    def __init__(self, left: Expression, right: Expression):
        super().__init__(left, right, "*")

    def evaluate(self) -> Any:
        return self.left.evaluate() * self.right.evaluate()


class DivisionExpression(BinaryExpression):
    def __init__(self, left: Expression, right: Expression):
        super().__init__(left, right, "/")

    def evaluate(self) -> Any:
        return self.left.evaluate() / self.right.evaluate()


class UnaryMinusExpression(Expression):
    def __init__(self, expression: Expression):
        self.expression: Expression = expression

    def evaluate(self) -> Any:
        return -self.expression.evaluate()

    def get_variables(self) -> dict[str, Variable]:
        variables = self.expression.get_variables()
        return variables

    def __str__(self):
        exp = self.expression.__str__()
        return f"-({exp})"

    def __repr__(self):
        exp = self.expression.__repr__()
        return f"UnaryMinusExpression({exp})"


class IntOperationExpression(Expression, ABC):
    def __init__(self, constant: int, expression: Expression, op: str = ""):
        self.expression = expression
        self.constant = constant
        self.op = op

    def get_variables(self) -> dict[str, Variable]:
        variables = self.expression.get_variables()
        return variables

    # def __str__(self):
    #     exp = self.expression.__str__()
    #     return f"({self.constant} {self.op} {exp}))"
    #
    # def __repr__(self):
    #     exp = self.expression.__repr__()
    #     return f"IntOperationExpression({self.constant},{exp},\'{self.op}\')"


class IntMultiplicationExpression(IntOperationExpression):
    def __init__(self, constant: int, expression: Expression):
        super().__init__(constant, expression)

    def evaluate(self) -> Any:
        val = self.expression.evaluate()
        val_type = type(val)
        return val * val_type(self.constant)

    def __str__(self):
        exp = self.expression.__str__()
        return f"({self.constant} * {exp})"

    def __repr__(self):
        exp = self.expression.__repr__()
        return f"IntMultiplicationExpression({self.constant},{exp})"


class IntDivisionExpression(IntOperationExpression):
    def __init__(self, constant: int, expression: Expression):
        super().__init__(constant, expression)

    def evaluate(self) -> Any:
        val = self.expression.evaluate()
        val_type = type(val)
        return val / val_type(self.constant)

    def __str__(self):
        exp = self.expression.__str__()
        return f"({exp} / {self.constant})"

    def __repr__(self):
        exp = self.expression.__repr__()
        return f"IntDivisionExpression({self.constant},{exp})"


class FunctionCallExpression(Expression):
    """Expression representing a mathematical function call.

    Supports functions of any arity:
    - 0-ary functions (constants like pi(), e())
    - Unary functions (sin(x), cos(x), etc.)
    - Binary functions (pow(x, y), etc.)
    - N-ary functions (custom functions)

    Function evaluation is delegated to the MathFunctions class.
    """

    def __init__(self, function_name: str, arguments: list[Expression]):
        """Initialize the function call expression.

        Args:
            function_name: Name of the function to call
            arguments: List of argument expressions (can be empty for 0-ary functions)

        Raises:
            ValueError: If the function is called with an incorrect number of arguments
        """
        from .value.math_functions import MathFunctions

        self.function_name = function_name
        self.arguments = (
            arguments if arguments else []
        )  # Ensure arguments is never None

        # Validate the number of arguments
        expected_arg_count = MathFunctions.get_argument_count(function_name)
        actual_arg_count = len(self.arguments)

        if expected_arg_count is not None and expected_arg_count != actual_arg_count:
            raise ValueError(
                f"Function '{function_name}' expects {expected_arg_count} arguments, but got {actual_arg_count}"
            )

    def evaluate(self) -> Any:
        from .value.math_functions import MathFunctions
        from .value.float_value import FloatValue

        # Extract values directly from argument expressions
        arg_values = [arg.evaluate().value for arg in self.arguments]

        # Delegate to MathFunctions class
        result = MathFunctions.evaluate(self.function_name, arg_values)

        # Always return FloatValue for consistency
        return FloatValue(result)

    def get_variables(self) -> dict[str, Variable]:
        variables = {}
        for arg in self.arguments:
            variables.update(arg.get_variables())
        return variables

    def __str__(self) -> str:
        args_str = ", ".join(str(arg) for arg in self.arguments)
        return f"{self.function_name}({args_str})"

    def __repr__(self) -> str:
        args_repr = ", ".join(repr(arg) for arg in self.arguments)
        return f"FunctionCallExpression('{self.function_name}', [{args_repr}])"
