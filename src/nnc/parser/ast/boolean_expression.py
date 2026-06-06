from abc import abstractmethod, ABC
from typing import Any

from .expression import Expression
from .variable import Variable


class BooleanExpression(Expression):
    @abstractmethod
    def evaluate(self) -> Any:
        pass  # pragma: no cover


class BooleanConstantExpression(BooleanExpression):
    value: bool

    def __init__(self, value: bool):
        self.value = value

    def evaluate(self) -> Any:
        return self.value

    def get_variables(self) -> dict[str, Variable]:
        return {}

    def __str__(self):
        return self.value.__str__()

    def __repr__(self):
        return f"BooleanConstantExpression({self.value})"


class BooleanTestExpression(BooleanExpression, ABC):
    def __init__(self, left: Expression, right: Expression, op: str = ""):
        self.left = left
        self.right = right
        self.op = op

    def __str__(self):
        ll = self.left.__str__()
        r = self.right.__str__()
        return f"({ll} {self.op} {r})"

    def __repr__(self):
        return f"BooleanTestExpression('{self.op}',{self.left.__repr__()},{self.right.__repr__()})"

    def get_variables(self) -> dict[str, Variable]:
        variables = self.left.get_variables()
        variables.update(self.right.get_variables())
        return variables


class BooleanGreaterTestExpression(BooleanTestExpression):
    def __init__(self, left: Expression, right: Expression):
        super().__init__(left, right, ">")

    def evaluate(self) -> Any:
        return self.left.evaluate() > self.right.evaluate()


class BooleanGreaterEqualTestExpression(BooleanTestExpression):
    def __init__(self, left: Expression, right: Expression):
        super().__init__(left, right, ">=")

    def evaluate(self) -> Any:
        return self.left.evaluate() >= self.right.evaluate()


class BooleanEqualTestExpression(BooleanTestExpression):
    def __init__(self, left: Expression, right: Expression):
        super().__init__(left, right, "==")

    def evaluate(self) -> Any:
        return self.left.evaluate() == self.right.evaluate()


class BooleanNotEqualTestExpression(BooleanTestExpression):
    def __init__(self, left: Expression, right: Expression):
        super().__init__(left, right, "!=")

    def evaluate(self) -> Any:
        return self.left.evaluate() != self.right.evaluate()


class BooleanLessTestExpression(BooleanTestExpression):
    def __init__(self, left: Expression, right: Expression):
        super().__init__(left, right, "<")

    def evaluate(self) -> Any:
        return self.left.evaluate() < self.right.evaluate()


class BooleanLessEqualTestExpression(BooleanTestExpression):
    def __init__(self, left: Expression, right: Expression):
        super().__init__(left, right, "<=")

    def evaluate(self) -> Any:
        return self.left.evaluate() <= self.right.evaluate()


class BooleanBinaryExpression(BooleanExpression, ABC):
    def __init__(self, left: BooleanExpression, right: BooleanExpression, op: str = ""):
        self.left = left
        self.right = right
        self.op = op

    def __str__(self):
        ll = self.left.__str__()
        r = self.right.__str__()
        return f"({ll} {self.op} {r})"

    def __repr__(self):
        return f"BooleanBinaryExpression('{self.op}',{self.left.__repr__()},{self.right.__repr__()})"

    def get_variables(self) -> dict[str, Variable]:
        variables = self.left.get_variables()
        variables.update(self.right.get_variables())
        return variables


class BooleanOrExpression(BooleanBinaryExpression):
    def __init__(self, left: BooleanExpression, right: BooleanExpression):
        super().__init__(left, right, "||")

    def evaluate(self) -> Any:
        return self.left.evaluate() or self.right.evaluate()


class BooleanAndExpression(BooleanBinaryExpression):
    def __init__(self, left: BooleanExpression, right: BooleanExpression):
        super().__init__(left, right, "&&")

    def evaluate(self) -> Any:
        return self.left.evaluate() and self.right.evaluate()


class BooleanNotExpression(BooleanExpression):
    def __init__(self, expression: BooleanExpression):
        self.expression = expression

    def evaluate(self) -> Any:
        return not self.expression.evaluate()

    def __str__(self):
        exp = self.expression.__str__()
        return f"!({exp})"

    def __repr__(self):
        return f"BooleanNotExpression({self.expression.__repr__()})"

    def get_variables(self) -> dict[str, Variable]:
        return self.expression.get_variables()
