"""Core TENNCell rule model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..parser.ast.boolean_expression import BooleanExpression
from ..parser.ast.expression import Expression
from ..parser.ast.variable import Variable

if TYPE_CHECKING:
    from ..inputs.yaml.locations import YamlLocation


class Rule:
    """A guarded production rule with one consumer variable.

    Args:
        consumer: Variable updated by the rule.
        producer: Expression producing the value to add to the consumer.
        guard: Boolean expression deciding whether the rule is active.

    Attributes:
        source_location: Physical YAML file and rule line for diagnostics, or
            ``None`` for rules constructed without YAML source metadata. This
            location remains attached if the rule is moved to another system.
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
        self.source_location: YamlLocation | None = None

    def __str__(self):
        """Render the rule in TENNCell source form."""
        g = self.guard.__str__()
        p = self.producer.__str__()
        return f"{g} : {p} -> {self.consumer}"

    def __repr__(self):
        """Return the string form for debugging."""
        return self.__str__()
