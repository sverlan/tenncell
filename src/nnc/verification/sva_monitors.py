"""Monitor-style SystemVerilog for generic properties (SVA backend).

Each sampling edge of the checker sees one trace row: the registers before the
edge, and the root inputs through their row-aligned copies. A monitor keeps
only the history its property needs; the result recorder (simulation only,
under ```ifndef FORMAL``) latches the earliest failure and prints one line per
property when the testbench calls ``sva_report``:

    SVA_RESULT <id> <status> <trigger_row|-> <reported_row|->
    SVA_OPEN <id> <trigger_row|end>

The statuses and rows are those of ``native`` on the same trace.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from .config import (
    ALWAYS,
    COVER,
    EVENTUALLY,
    EVENTUALLY_WITHIN,
    NEVER,
    PERSISTENCE,
    RESPONSE_AFTER,
    RESPONSE_WITHIN,
)
from .sva import SelectedProperty

REPORT_TASK = "sva_report"
# Replay check: did a property first fail, or a cover first hit, on a row?
REPLAY_TASK = "sva_replay_check"
# Arguments of the replay check task.
EXPECTED_ROW = "sva_expected_row"
REPRODUCED = "sva_reproduced"
# Variables local to the report task.
LOOP_INDEX = "sva_k"
LOOP_FOUND = "sva_found"
STEP_COUNTER = "sva_step"
# Kind of a formal liveness check (unbounded eventually).
LIVE = "live"


@dataclass(slots=True)
class MonitorCode:
    """Checker code for the selected properties, by section."""

    step_counter: list[str] = field(default_factory=list)
    # Monitor history bits (counters, pending vectors, flags), without the
    # input copies and the simulation-only result diagnostics.
    control_bits: int = 0
    # Formal checks: (property ID, "assert", "cover" or "live", combinational
    # signal that is true when the row violates the property, hits the cover,
    # or, for "live", once the property is satisfied: it must eventually hold).
    formal_checks: list[tuple[str, str, str]] = field(default_factory=list)
    # Invariants of the monitor state (label base, expression), asserted in
    # formal builds: they hold in every reachable state and exclude the
    # unreachable ones (a counter above its limit) from induction proofs.
    formal_invariants: list[tuple[str, str]] = field(default_factory=list)
    monitors: list[str] = field(default_factory=list)
    recorders: list[str] = field(default_factory=list)
    report: list[str] = field(default_factory=list)
    replay: list[str] = field(default_factory=list)


def emit_monitors(
    properties: tuple[SelectedProperty, ...],
    conditions: dict[str, str],
    triggers: dict[str, str],
    weak: bool,
    clock: str,
    reset: str,
    reset_active_high: bool,
    row_counter: str,
    fresh_name: Callable[[str], str],
) -> MonitorCode:
    """Emit monitors, result recorders and the report task.

    Args:
        properties: Selected properties.
        conditions: Rendered checker expression of each property condition,
            keyed by property ID.
        triggers: Rendered trigger of each `when` property, keyed by ID.
        weak: Whether open obligations are reported as ``pending``.
        clock: Clock signal.
        reset: Asynchronous reset signal.
        reset_active_high: Whether the reset is active high.
        row_counter: The 64-bit simulation row counter.
        fresh_name: Returns an unused identifier based on its argument.
    """
    code = MonitorCode()
    reset_edge = "posedge" if reset_active_high else "negedge"
    reset_condition = reset if reset_active_high else f"!{reset}"
    sequential = f"always_ff @(posedge {clock} or {reset_edge} {reset}) begin"
    step = _StepCounter(properties, fresh_name)
    code.step_counter = step.declaration(sequential, reset_condition)
    code.control_bits = step.width if step.used else 0
    if step.used:
        code.formal_invariants.append(
            (f"{step.name}_invariant", step.at_most(step.limit))
        )
    failed_any = "failed"
    report = [
        f"task automatic {REPORT_TASK}(output bit {failed_any});",
        f"    {failed_any} = 1'b0;",
    ]
    last_row = f"({row_counter} - 64'd1)"
    uses_task_loop = False
    replay_terms: list[str] = []
    for selected in properties:
        prop = selected.bound.property
        pid = prop.id
        names = _Names(pid, fresh_name)
        cond = names.new("cond")
        active = step.at_least(prop.from_step)
        lines = [
            f"// {pid} ({prop.kind}): {prop.condition_key} {' '.join(prop.condition.split())}"
            + (f", from_step {prop.from_step}" if prop.from_step else ""),
            f"logic {cond};",
            f"assign {cond} = {conditions[pid]};",
        ]
        recorder: list[str] = []
        if prop.kind in (ALWAYS, NEVER):
            failed_now = names.new("failed_now")
            bad = f"!{cond}" if prop.kind == ALWAYS else cond
            lines += [
                f"logic {failed_now};",
                f"assign {failed_now} = {_and(active, bad)};",
            ]
            failed, row = names.new("failed"), names.new("reported_row")
            recorder += _latch(
                sequential, reset_condition, failed_now, failed, row, row_counter
            )
            report += [
                f"    if ({failed}) begin",
                f'        $display("SVA_RESULT {pid} fail - %0d", {row});',
                f"        {failed_any} = 1'b1;",
                "    end else begin",
                f'        $display("SVA_RESULT {pid} pass - -");',
                "    end",
            ]
        elif prop.kind == COVER:
            hit_now, covered = names.new("hit_now"), names.new("covered")
            hit_row = names.new("hit_row")
            lines += [f"logic {hit_now};", f"assign {hit_now} = {_and(active, cond)};"]
            # The first hit and its row (for the replay check).
            recorder += _latch(
                sequential, reset_condition, hit_now, covered, hit_row, row_counter
            )
            code.control_bits += 1
            report += [
                f"    if ({covered}) begin",
                f'        $display("SVA_RESULT {pid} covered - -");',
                "    end else begin",
                f'        $display("SVA_RESULT {pid} not_covered - -");',
                "    end",
            ]
        elif prop.kind == EVENTUALLY:
            # Satisfied on an earlier row (seen) or on this one (hit_now); the
            # formal liveness check requires it to become true eventually.
            seen, hit_now = names.new("seen"), names.new("hit_now")
            lines += [f"logic {hit_now};", f"assign {hit_now} = {_and(active, cond)};"]
            lines += _flag(sequential, reset_condition, hit_now, seen)
            satisfied = f"{seen} || {hit_now}"
            code.control_bits += 1
            report += [
                f"    if ({seen}) begin",
                f'        $display("SVA_RESULT {pid} pass - -");',
                "    end else begin",
                *_open_end(pid, weak, last_row, failed_any),
                "    end",
            ]
        elif prop.kind == EVENTUALLY_WITHIN:
            assert prop.within is not None
            first = prop.from_step + prop.within[0]
            last = prop.from_step + prop.within[1]
            seen, failed_now = names.new("seen"), names.new("failed_now")
            in_window = _and(step.at_least(first), step.at_most(last))
            lines += _flag(sequential, reset_condition, _and(in_window, cond), seen)
            code.control_bits += 1
            lines += [
                f"logic {failed_now};",
                f"assign {failed_now} = {step.equals(last)} && !({seen} || {cond});",
            ]
            failed, row = names.new("failed"), names.new("reported_row")
            recorder += _latch(
                sequential, reset_condition, failed_now, failed, row, row_counter
            )
            report += [
                f"    if ({failed}) begin",
                f'        $display("SVA_RESULT {pid} fail - %0d", {row});',
                f"        {failed_any} = 1'b1;",
                f"    end else if ({seen}) begin",
                f'        $display("SVA_RESULT {pid} pass - -");',
                "    end else begin",
                *_open_end(pid, weak, last_row, failed_any),
                "    end",
            ]
        elif prop.kind in (RESPONSE_AFTER, RESPONSE_WITHIN):
            trigger = names.new("trigger")
            lines.insert(1, f"logic {trigger};")
            lines.insert(2, f"assign {trigger} = {_and(active, triggers[pid])};")
            if prop.kind == RESPONSE_AFTER:
                assert prop.after is not None
                first, depth = prop.after, prop.after
            else:
                assert prop.within is not None
                first, depth = prop.within
            # pending[k]: a trigger k rows ago whose obligation is still open.
            pending = names.new("pending")
            failed_now = names.new("failed_now")
            due = f"{pending}[{depth}]" if depth else trigger
            code.control_bits += depth
            if depth:
                lines += _pending(
                    sequential, reset_condition, pending, depth, trigger, cond, first
                )
            lines += [
                f"logic {failed_now};",
                f"assign {failed_now} = {due} && !{cond};",
            ]
            failed, row = names.new("failed"), names.new("reported_row")
            trigger_row = names.new("trigger_row")
            recorder += _latch(
                sequential,
                reset_condition,
                failed_now,
                failed,
                row,
                row_counter,
                trigger_row,
                f"{row_counter} - 64'd{depth}",
            )
            report += [
                f"    if ({failed}) begin",
                f'        $display("SVA_RESULT {pid} fail %0d %0d", {trigger_row}, {row});',
                f"        {failed_any} = 1'b1;",
            ]
            if depth:
                uses_task_loop = True
                report += [
                    f"    end else if (|{pending}) begin",
                    *_open_triggers(
                        pid, weak, pending, depth, row_counter, last_row, failed_any
                    ),
                ]
            report += [
                "    end else begin",
                f'        $display("SVA_RESULT {pid} pass - -");',
                "    end",
            ]
        elif prop.kind == PERSISTENCE:
            assert prop.after is not None
            trigger = names.new("trigger")
            lines.insert(1, f"logic {trigger};")
            lines.insert(2, f"assign {trigger} = {_and(active, triggers[pid])};")
            armed, failed_now = names.new("armed"), names.new("failed_now")
            lines += _flag(sequential, reset_condition, trigger, armed)
            code.control_bits += 1
            if prop.after == 0:
                holding = f"({armed} || {trigger})"
            else:
                # Rows since the first trigger, saturating at `after`.
                age = names.new("age")
                width = max(1, prop.after.bit_length())
                code.control_bits += width
                limit = f"{width}'d{prop.after}"
                lines += [
                    f"logic [{width - 1}:0] {age};",
                    sequential,
                    f"    if ({reset_condition}) begin",
                    f"        {age} <= {width}'d0;",
                    f"    end else if (({armed} || {trigger}) && {age} != {limit}) begin",
                    f"        {age} <= {age} + {width}'d1;",
                    "    end",
                    "end",
                ]
                holding = f"({armed} && {age} == {limit})"
                # The age counts from the first trigger and stops at `after`.
                code.formal_invariants.append(
                    (
                        f"sva_{pid}_age_invariant",
                        f"({age} <= {limit}) && ({armed} || {age} == {width}'d0)",
                    )
                )
            lines += [
                f"logic {failed_now};",
                f"assign {failed_now} = {holding} && !{cond};",
            ]
            failed, row = names.new("failed"), names.new("reported_row")
            first_row, trigger_row = (
                names.new("first_trigger_row"),
                names.new("trigger_row"),
            )
            recorder += [
                f"logic [63:0] {first_row};",
                sequential,
                f"    if ({reset_condition}) begin",
                f"        {first_row} <= 64'd0;",
                f"    end else if ({trigger} && !{armed}) begin",
                f"        {first_row} <= {row_counter};",
                "    end",
                "end",
            ]
            recorder += _latch(
                sequential,
                reset_condition,
                failed_now,
                failed,
                row,
                row_counter,
                trigger_row,
                f"({armed} ? {first_row} : {row_counter})",
            )
            report += [
                f"    if ({failed}) begin",
                f'        $display("SVA_RESULT {pid} fail %0d %0d", {trigger_row}, {row});',
                f"        {failed_any} = 1'b1;",
                "    end else begin",
                f'        $display("SVA_RESULT {pid} pass - -");',
                "    end",
            ]
        else:  # pragma: no cover - every kind is handled above
            raise ValueError(f"property kind {prop.kind} is not monitored")
        # First failure (or first cover hit) and its row: what a bmc or cover
        # witness ends with. Unbounded eventually never fails on a row.
        if prop.kind == COVER:
            replay_terms.append(f"({covered} && {hit_row} == {EXPECTED_ROW})")
        elif prop.kind != EVENTUALLY:
            replay_terms.append(f"({failed} && {row} == {EXPECTED_ROW})")
        # Unbounded eventually is liveness, not a safety violation on a row.
        if prop.kind == COVER:
            code.formal_checks.append((pid, "cover", hit_now))
        elif prop.kind == EVENTUALLY:
            code.formal_checks.append((pid, LIVE, satisfied))
        else:
            code.formal_checks.append((pid, "assert", failed_now))
        code.monitors += [*lines, ""]
        if recorder:
            code.recorders += [*recorder, ""]
    if uses_task_loop:
        report[1:1] = [f"    int {LOOP_INDEX};", f"    bit {LOOP_FOUND};"]
    report.append("endtask")
    code.report = report
    reproduced = " || ".join(replay_terms) if replay_terms else "1'b0"
    code.replay = [
        f"task automatic {REPLAY_TASK}(input logic [63:0] {EXPECTED_ROW}, "
        f"output bit {REPRODUCED});",
        f"    {REPRODUCED} = {reproduced};",
        "endtask",
    ]
    return code


def _pending(
    sequential: str,
    reset_condition: str,
    pending: str,
    depth: int,
    trigger: str,
    cond: str,
    first: int,
) -> list[str]:
    """Age-indexed pending obligations ``[depth:1]`` of a response property.

    At each row the bit of age ``k`` is cleared when the condition holds and
    ``k >= first`` (inside the window), then every bit ages by one row.
    """
    enter = f"{trigger} && !{cond}" if first == 0 else trigger
    lines = [
        f"logic [{depth}:1] {pending};",
        sequential,
        f"    if ({reset_condition}) begin",
        f"        {pending} <= '0;",
        "    end else begin",
        f"        {pending}[1] <= {enter};",
    ]
    if depth >= 2:
        if first <= 1:
            lines.append(
                f"        {pending}[{depth}:2] <= {pending}[{depth - 1}:1] & ~{{{depth - 1}{{{cond}}}}};"
            )
        else:
            # Ages below `first` are outside the window: only age.
            lines += [
                f"        {pending}[{min(first, depth)}:2] <= {pending}[{min(first, depth) - 1}:1];",
                *(
                    [
                        f"        {pending}[{depth}:{first + 1}] <= "
                        f"{pending}[{depth - 1}:{first}] & ~{{{depth - first}{{{cond}}}}};"
                    ]
                    if depth > first
                    else []
                ),
            ]
    lines += ["    end", "end"]
    return lines


def _open_triggers(
    pid: str,
    weak: bool,
    pending: str,
    depth: int,
    row_counter: str,
    last_row: str,
    failed_any: str,
) -> list[str]:
    """Report lines for the pending obligations at the end, oldest first.

    After the last edge, bit ``k`` belongs to the trigger ``k`` rows before
    ``row_counter`` (one past the last row).
    """
    loop = f"for ({LOOP_INDEX} = {depth}; {LOOP_INDEX} >= 1; {LOOP_INDEX} = {LOOP_INDEX} - 1)"
    trigger_row = f"{row_counter} - 64'({LOOP_INDEX})"
    if weak:
        return [
            f'        $display("SVA_RESULT {pid} pending - -");',
            f"        {loop}",
            f"            if ({pending}[{LOOP_INDEX}])",
            f'                $display("SVA_OPEN {pid} %0d", {trigger_row});',
        ]
    # Strict: the earliest open obligation fails at the last row.
    return [
        f"        {LOOP_FOUND} = 1'b0;",
        f"        {loop}",
        f"            if ({pending}[{LOOP_INDEX}] && !{LOOP_FOUND}) begin",
        f'                $display("SVA_RESULT {pid} fail %0d %0d", {trigger_row}, {last_row});',
        f"                {LOOP_FOUND} = 1'b1;",
        "            end",
        f"        {failed_any} = 1'b1;",
    ]


def _open_end(pid: str, weak: bool, last_row: str, failed_any: str) -> list[str]:
    """Report lines for an obligation still open at the end (no trigger row)."""
    if weak:
        return [
            f'        $display("SVA_RESULT {pid} pending - -");',
            f'        $display("SVA_OPEN {pid} end");',
        ]
    return [
        f'        $display("SVA_RESULT {pid} fail - %0d", {last_row});',
        f"        {failed_any} = 1'b1;",
    ]


def _latch(
    sequential: str,
    reset_condition: str,
    failed_now: str,
    failed: str,
    row: str,
    row_counter: str,
    trigger_row: str | None = None,
    trigger_value: str | None = None,
) -> list[str]:
    """Latch the first failure, the row where it was detected and, for
    triggered properties, the row of the trigger it belongs to."""
    keep = trigger_row is not None
    return [
        f"logic {failed};",
        f"logic [63:0] {row};",
        *([f"logic [63:0] {trigger_row};"] if keep else []),
        sequential,
        f"    if ({reset_condition}) begin",
        f"        {failed} <= 1'b0;",
        f"        {row} <= 64'd0;",
        *([f"        {trigger_row} <= 64'd0;"] if keep else []),
        f"    end else if ({failed_now} && !{failed}) begin",
        f"        {failed} <= 1'b1;",
        f"        {row} <= {row_counter};",
        *([f"        {trigger_row} <= {trigger_value};"] if keep else []),
        "    end",
        "end",
    ]


def _flag(sequential: str, reset_condition: str, set_when: str, flag: str) -> list[str]:
    """A flag cleared by reset and set (for good) when ``set_when`` holds."""
    return [
        f"logic {flag};",
        sequential,
        f"    if ({reset_condition}) begin",
        f"        {flag} <= 1'b0;",
        f"    end else if ({set_when}) begin",
        f"        {flag} <= 1'b1;",
        "    end",
        "end",
    ]


def _and(left: str, right: str) -> str:
    if left == "1'b1":
        return right
    return f"{left} && {right}"


class _Names:
    """Generated identifiers of one property, all prefixed with ``sva_<id>``."""

    def __init__(self, pid: str, fresh_name: Callable[[str], str]):
        self.pid = pid
        self.fresh_name = fresh_name

    def new(self, role: str) -> str:
        return self.fresh_name(f"sva_{self.pid}_{role}")


class _StepCounter:
    """Saturating row position shared by ``from_step`` and windows.

    It counts sampled rows from 0 and stops one above the largest row any
    property compares with, so comparisons with every needed row are exact.
    """

    def __init__(
        self,
        properties: tuple[SelectedProperty, ...],
        fresh_name: Callable[[str], str],
    ):
        needed = 0
        windows = False
        for selected in properties:
            prop = selected.bound.property
            needed = max(needed, prop.from_step)
            if prop.kind == EVENTUALLY_WITHIN:
                assert prop.within is not None
                needed = max(needed, prop.from_step + prop.within[1])
                windows = True
        self.used = needed > 0 or windows
        self.limit = needed + 1
        self.width = max(1, self.limit.bit_length())
        self.name = fresh_name(STEP_COUNTER) if self.used else ""

    def literal(self, value: int) -> str:
        return f"{self.width}'d{value}"

    def at_least(self, row: int) -> str:
        if row == 0:
            return "1'b1"
        return f"({self.name} >= {self.literal(row)})"

    def at_most(self, row: int) -> str:
        return f"({self.name} <= {self.literal(row)})"

    def equals(self, row: int) -> str:
        return f"({self.name} == {self.literal(row)})"

    def declaration(self, sequential: str, reset_condition: str) -> list[str]:
        if not self.used:
            return []
        return [
            f"// Row position for from_step and windows; saturates at {self.limit}.",
            f"logic [{self.width - 1}:0] {self.name};",
            sequential,
            f"    if ({reset_condition}) begin",
            f"        {self.name} <= {self.literal(0)};",
            f"    end else if ({self.name} != {self.literal(self.limit)}) begin",
            f"        {self.name} <= {self.name} + {self.literal(1)};",
            "    end",
            "end",
            "",
        ]
