"""Core TENNCell rule model."""

from ..parser.ast.boolean_expression import BooleanExpression
from ..parser.ast.expression import Expression
from ..parser.ast.variable import Variable


class Rule:
    """A guarded production rule with one consumer variable.

    Args:
        consumer: Variable updated by the rule.
        producer: Expression producing the value to add to the consumer.
        guard: Boolean expression deciding whether the rule is active.
    """

    guard: BooleanExpression
    producer: Expression
    consumer: Variable
    vars: dict[str, Variable]

    def __init__(
        self, consumer: Variable, producer: Expression, guard: BooleanExpression
    ):
        """Create a rule from its consumer, producer, and guard expressions.

        Args:
            consumer: Variable updated by the rule.
            producer: Expression producing the value to add to the consumer.
            guard: Boolean expression deciding whether the rule is active.
        """
        self.guard = guard
        self.producer = producer
        self.consumer = consumer
        self.vars: dict[str, Variable] = producer.get_variables()

    def __str__(self):
        """Render the rule in TENNCell source form."""
        g = self.guard.__str__()
        p = self.producer.__str__()
        return f"{g} : {p} -> {self.consumer}"

    def __repr__(self):
        """Return the string form for debugging."""
        return self.__str__()
