"""The built-in ``native`` checker: evaluate generic properties on a trace.

Temporal offsets (``after``, ``within``, ``from_step``) count trace rows, as MC2's
``X`` does. Labels (step or time values) are only used for reporting. The
semantics follow ``docs/verification.md`` section 6 (native truth table).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ...model.evaluation import evaluate_boolean
from ...parser.ast import BooleanExpression, VariableExpression
from ...parser.ast.value import FloatValue
from ...parser.ast.value.math_functions import MathFunctions
from ..binding import BoundVerification
from ..config import (
    ALWAYS,
    COVER,
    EVENTUALLY,
    EVENTUALLY_WITHIN,
    NEVER,
    PERSISTENCE,
    RESPONSE_AFTER,
    RESPONSE_WITHIN,
    TRACE_SEMANTICS,
)
from .binding import BoundProperty

if TYPE_CHECKING:
    from ...model.system import NncSystem

PASS = "pass"
FAIL = "fail"
PENDING = "pending"
COVERED = "covered"
NOT_COVERED = "not_covered"
SKIPPED = "skipped"
NATIVE = "native"

Label = int | float


class VerificationError(ValueError):
    """An operational verification error (bad trace, evaluation failure)."""


@dataclass(frozen=True)
class Trace:
    """A finite trace: one row of column values per time point.

    Args:
        labels: Step or time label of each row, finite and strictly increasing.
        rows: Column values of each row; every row has the same columns.

    Raises:
        VerificationError: If the trace is empty, the lengths differ, a label is
            not finite or not strictly increasing, or rows have different columns.
    """

    labels: Sequence[Label]
    rows: Sequence[dict[str, float]]

    def __post_init__(self) -> None:
        if len(self.labels) != len(self.rows):
            raise VerificationError(
                f"Trace has {len(self.labels)} labels but {len(self.rows)} rows"
            )
        if not self.rows:
            raise VerificationError("Trace has no rows")
        previous: Label | None = None
        for index, label in enumerate(self.labels):
            if not math.isfinite(label):
                raise VerificationError(f"Trace label at row {index} is not finite")
            if previous is not None and label <= previous:
                raise VerificationError(
                    f"Trace labels must be strictly increasing: row {index} has "
                    f"{label} after {previous}"
                )
            previous = label
        columns = set(self.rows[0])
        for index, row in enumerate(self.rows):
            if set(row) != columns:
                raise VerificationError(
                    f"Trace row {index} does not have the same columns as row 0"
                )

    @property
    def columns(self) -> frozenset[str]:
        """Return the trace's column names."""
        return frozenset(self.rows[0])


@dataclass(frozen=True)
class Obligation:
    """An obligation still open at the end of the trace (weak semantics)."""

    trigger_row: int | None
    trigger_label: Label | None


@dataclass(frozen=True)
class PropertyResult:
    """Outcome of checking one generic property.

    Args:
        id: Property identifier.
        kind: Property kind.
        status: ``pass``, ``fail``, ``pending``, ``covered``, ``not_covered``,
            or ``skipped``.
        trigger_row: Row opening the reported failed obligation (trigger kinds).
        trigger_label: Label of ``trigger_row``.
        reported_row: Row at which the reported failure became known.
        reported_label: Label of ``reported_row``.
        open_obligations: Obligations still open at the end (``pending`` only).
    """

    id: str
    kind: str
    status: str
    trigger_row: int | None = None
    trigger_label: Label | None = None
    reported_row: int | None = None
    reported_label: Label | None = None
    open_obligations: tuple[Obligation, ...] = field(default_factory=tuple)


class _RowContext:
    """Evaluation context reading one trace row."""

    def __init__(self, system: "NncSystem", row: dict[str, float]):
        self.system = system
        self.row = row

    def variable_value(self, node: VariableExpression) -> FloatValue:
        return FloatValue(self.row[node.variable.name])

    def reference_value(self, reference: str) -> FloatValue:
        constant = reference.replace(".", "__")
        if constant in self.system.constants:
            return self.system.constants[constant]
        return FloatValue(self.row[constant])

    def call_function(self, name: str, arguments: list[float]) -> FloatValue:
        return FloatValue(MathFunctions.evaluate(name, arguments))


def check_properties(
    bound: BoundVerification,
    system: "NncSystem",
    trace: Trace,
    trace_semantics: str | None = None,
) -> list[PropertyResult]:
    """Check every generic property against a trace with ``native`` semantics.

    Properties whose ``targets`` exclude ``native`` are reported as ``skipped``
    and their columns are not required.

    Args:
        bound: Verification config bound to ``system``.
        system: The TENNCell system, used for constants and FSM states.
        trace: The trace to check.
        trace_semantics: ``strict`` or ``weak``; defaults to the ``native``
            backend's effective setting.

    Returns:
        One result per property, in YAML order.

    Raises:
        VerificationError: If a checked property needs a column that is missing
            from the trace or holds a non-finite value, or if evaluating a
            condition fails.
    """
    if trace_semantics is None:
        trace_semantics = bound.config.effective_trace_semantics(NATIVE)
    if trace_semantics not in TRACE_SEMANTICS:
        raise VerificationError(
            f"trace_semantics must be one of {', '.join(TRACE_SEMANTICS)}, "
            f"not {trace_semantics!r}"
        )
    weak = trace_semantics == "weak"
    checked = [p for p in bound.properties if p.property.targets_backend(NATIVE)]
    _check_columns(checked, trace)
    results = []
    for prop in bound.properties:
        if not prop.property.targets_backend(NATIVE):
            results.append(
                PropertyResult(prop.property.id, prop.property.kind, SKIPPED)
            )
        else:
            results.append(_Checker(prop, system, trace, weak).run())
    return results


def _check_columns(properties: list[BoundProperty], trace: Trace) -> None:
    columns = trace.columns
    for prop in properties:
        for column in prop.columns:
            if column not in columns:
                raise VerificationError(
                    f"Property '{prop.property.id}': trace has no column '{column}'"
                )
            for index, row in enumerate(trace.rows):
                if not math.isfinite(row[column]):
                    raise VerificationError(
                        f"Property '{prop.property.id}': column '{column}' is not "
                        f"finite at row {index} (label {trace.labels[index]})"
                    )


class _Checker:
    """Evaluate one property on a trace following the native truth table."""

    def __init__(
        self, prop: BoundProperty, system: "NncSystem", trace: Trace, weak: bool
    ):
        self.prop = prop
        self.system = system
        self.trace = trace
        self.weak = weak
        self.length = len(trace.rows)
        self._condition_cache: dict[int, bool] = {}
        self._trigger_cache: dict[int, bool] = {}

    def run(self) -> PropertyResult:
        kind = self.prop.property.kind
        handler: Callable[[], PropertyResult] = {
            ALWAYS: self._always,
            NEVER: self._never,
            EVENTUALLY: self._eventually,
            EVENTUALLY_WITHIN: self._eventually_within,
            RESPONSE_AFTER: self._response_after,
            RESPONSE_WITHIN: self._response_within,
            PERSISTENCE: self._persistence,
            COVER: self._cover,
        }[kind]
        return handler()

    # Evaluation -----------------------------------------------------------

    def condition(self, row: int) -> bool:
        if row not in self._condition_cache:
            self._condition_cache[row] = self._evaluate(
                self.prop.condition, self.prop.property.condition_key, row
            )
        return self._condition_cache[row]

    def trigger(self, row: int) -> bool:
        assert self.prop.trigger is not None
        if row not in self._trigger_cache:
            self._trigger_cache[row] = self._evaluate(self.prop.trigger, "when", row)
        return self._trigger_cache[row]

    def _evaluate(self, expression: BooleanExpression, role: str, row: int) -> bool:
        try:
            return bool(
                evaluate_boolean(
                    expression, _RowContext(self.system, self.trace.rows[row])
                )
            )
        except Exception as error:
            raise VerificationError(
                f"Property '{self.prop.property.id}': evaluating the '{role}' "
                f"condition at row {row} (label {self.trace.labels[row]}) failed: "
                f"{error}"
            ) from error

    # Results --------------------------------------------------------------

    def _result(self, status: str, **fields) -> PropertyResult:
        return PropertyResult(
            self.prop.property.id, self.prop.property.kind, status, **fields
        )

    def _fail(
        self, reported_row: int, trigger_row: int | None = None
    ) -> PropertyResult:
        labels = self.trace.labels
        return self._result(
            FAIL,
            trigger_row=trigger_row,
            trigger_label=labels[trigger_row] if trigger_row is not None else None,
            reported_row=reported_row,
            reported_label=labels[reported_row],
        )

    def _open(self, open_triggers: Sequence[int | None]) -> PropertyResult:
        """Result for obligations still open at the end of the trace."""
        if not self.weak:
            # Strict: open obligations fail at the last row; report the earliest.
            return self._fail(self.length - 1, open_triggers[0])
        labels = self.trace.labels
        return self._result(
            PENDING,
            open_obligations=tuple(
                Obligation(t, labels[t] if t is not None else None)
                for t in open_triggers
            ),
        )

    def _rows(self) -> range:
        return range(self.prop.property.from_step, self.length)

    # Kinds ----------------------------------------------------------------

    def _always(self) -> PropertyResult:
        for row in self._rows():
            if not self.condition(row):
                return self._fail(row)
        return self._result(PASS)

    def _never(self) -> PropertyResult:
        for row in self._rows():
            if self.condition(row):
                return self._fail(row)
        return self._result(PASS)

    def _eventually(self) -> PropertyResult:
        if any(self.condition(row) for row in self._rows()):
            return self._result(PASS)
        return self._open([None])

    def _cover(self) -> PropertyResult:
        if any(self.condition(row) for row in self._rows()):
            return self._result(COVERED)
        return self._result(NOT_COVERED)

    def _eventually_within(self) -> PropertyResult:
        assert self.prop.property.within is not None
        start, end = self.prop.property.within
        base = self.prop.property.from_step
        outcome = self._window(base + start, base + end)
        if outcome == PASS:
            return self._result(PASS)
        if outcome == FAIL:
            return self._fail(base + end)
        return self._open([None])

    def _window(self, first: int, last: int) -> str:
        """Check that the condition holds on some row of ``first..last``.

        Returns ``pass``, ``fail`` (window complete inside the trace without the
        condition), or ``pending`` (window reaches past the end, not yet seen).
        """
        for row in range(first, min(last, self.length - 1) + 1):
            if self.condition(row):
                return PASS
        return FAIL if last <= self.length - 1 else PENDING

    def _triggers(self) -> list[int]:
        return [row for row in self._rows() if self.trigger(row)]

    def _response_after(self) -> PropertyResult:
        assert self.prop.property.after is not None
        offset = self.prop.property.after
        return self._response(lambda t: (t + offset, t + offset))

    def _response_within(self) -> PropertyResult:
        assert self.prop.property.within is not None
        start, end = self.prop.property.within
        return self._response(lambda t: (t + start, t + end))

    def _response(self, window: Callable[[int], tuple[int, int]]) -> PropertyResult:
        failures: list[tuple[int, int]] = []  # (reported_row, trigger_row)
        open_triggers: list[int] = []
        for trigger_row in self._triggers():
            first, last = window(trigger_row)
            outcome = self._window(first, last)
            if outcome == FAIL:
                failures.append((last, trigger_row))
            elif outcome == PENDING:
                open_triggers.append(trigger_row)
        if not self.weak:
            # Strict: an obligation still open at the end fails at the last row.
            failures.extend((self.length - 1, t) for t in open_triggers)
            open_triggers = []
        if failures:
            # Earliest detection row; ties go to the earliest trigger.
            reported_row, trigger_row = min(failures)
            return self._fail(reported_row, trigger_row)
        if open_triggers:
            return self._open(open_triggers)
        return self._result(PASS)

    def _persistence(self) -> PropertyResult:
        assert self.prop.property.after is not None
        triggers = self._triggers()
        if not triggers:
            return self._result(PASS)
        first_trigger = triggers[0]
        for row in range(first_trigger + self.prop.property.after, self.length):
            if not self.condition(row):
                # The earliest trigger's obligation is the first one to cover `row`.
                return self._fail(row, first_trigger)
        return self._result(PASS)
