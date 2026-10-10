"""Concurrent-style SystemVerilog for generic properties (``--sva-style concurrent``).

Each property becomes one ``assert property`` (``cover property`` for
``cover``), clocked by the checker clock and disabled during reset, for
simulators with full SVA support. The encodings follow ``native`` under
``strict`` semantics (``weak`` is rejected for this style): obligations still
open at the end of the run use strong operators, so they fail when the run
ends. There is no result recorder: a failure is reported by the tool, with an
``SVA_FAIL <id> row <row>`` message from the action block (the row the
assertion was evaluated on, ``$sampled`` of the row counter).

Row ``0`` is the first sampling edge after reset. A saturating row counter
gives ``from_step`` and anchors the properties that start on row ``0``.

| Kind | Property |
|---|---|
| ``always P`` | ``active |-> P`` |
| ``never P`` | ``active |-> !P`` |
| ``eventually P`` | ``first |-> strong(##[f:$] P)`` |
| ``eventually P within [a, b]`` | ``first |-> strong(##[f+a:f+b] P)`` |
| ``when T then P after n`` | ``active && T |-> strong(##[n:n] P)`` (``P`` for ``n = 0``) |
| ``when T then P within [a, b]`` | ``active && T |-> strong(##[a:b] P)`` (``P`` for ``[0, 0]``) |
| ``when T then_always P after n`` | ``active && T |-> nexttime[n] always P`` (weak) |
| ``cover P`` | ``cover property (active && P)`` |

``active`` is ``row >= from_step``; ``first`` is row ``0``.
"""

from __future__ import annotations

from collections.abc import Callable

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
from .sva_monitors import STEP_COUNTER, MonitorCode


def emit_concurrent(
    properties: tuple[SelectedProperty, ...],
    conditions: dict[str, str],
    triggers: dict[str, str],
    clock: str,
    reset: str,
    reset_active_high: bool,
    row_counter: str,
    fresh_name: Callable[[str], str],
) -> MonitorCode:
    """Emit the row counter and one concurrent assertion per property.

    Args:
        properties: Selected properties.
        conditions: Rendered condition of each property, keyed by ID.
        triggers: Rendered trigger of each ``when`` property, keyed by ID.
        clock: Clock signal.
        reset: Asynchronous reset signal.
        reset_active_high: Whether the reset is active high.
        row_counter: The 64-bit simulation row counter, for messages.
        fresh_name: Returns an unused identifier based on its argument.

    Returns:
        The code; ``monitors`` holds the assertions, ``recorders`` and
        ``report`` are empty.
    """
    code = MonitorCode()
    if not properties:
        return code
    reset_edge = "posedge" if reset_active_high else "negedge"
    reset_condition = reset if reset_active_high else f"!{reset}"
    # Saturates one above the largest from_step: comparisons stay exact.
    limit = max(selected.bound.property.from_step for selected in properties) + 1
    width = max(1, limit.bit_length())
    step = fresh_name(STEP_COUNTER)
    code.control_bits = width
    code.step_counter = [
        f"// Row position (row 0 is the first edge after reset); saturates at {limit}.",
        f"logic [{width - 1}:0] {step};",
        f"always_ff @(posedge {clock} or {reset_edge} {reset}) begin",
        f"    if ({reset_condition}) begin",
        f"        {step} <= {width}'d0;",
        f"    end else if ({step} != {width}'d{limit}) begin",
        f"        {step} <= {step} + {width}'d1;",
        "    end",
        "end",
        "",
    ]
    clocking = f"@(posedge {clock}) disable iff ({reset_condition})"
    first = f"({step} == {width}'d0)"
    for selected in properties:
        prop = selected.bound.property
        pid = prop.id
        f = prop.from_step
        active = f"({step} >= {width}'d{f})" if f else ""
        cond = f"({conditions[pid]})"
        if prop.kind in (ALWAYS, NEVER):
            body = cond if prop.kind == ALWAYS else f"!{cond}"
            prop_text = f"{active} |-> {body}" if active else body
        elif prop.kind == EVENTUALLY:
            prop_text = f"{first} |-> strong(##[{f}:$] {cond})"
        elif prop.kind == EVENTUALLY_WITHIN:
            assert prop.within is not None
            a, b = prop.within
            prop_text = f"{first} |-> strong(##[{f + a}:{f + b}] {cond})"
        elif prop.kind in (RESPONSE_AFTER, RESPONSE_WITHIN, PERSISTENCE):
            trigger = f"({triggers[pid]})"
            antecedent = f"{active} && {trigger}" if active else trigger
            if prop.kind == PERSISTENCE:
                assert prop.after is not None
                later = f"nexttime[{prop.after}] " if prop.after else ""
                consequent = f"{later}always {cond}"
            else:
                if prop.kind == RESPONSE_AFTER:
                    assert prop.after is not None
                    a = b = prop.after
                else:
                    assert prop.within is not None
                    a, b = prop.within
                consequent = cond if b == 0 else f"strong(##[{a}:{b}] {cond})"
            prop_text = f"{antecedent} |-> {consequent}"
        elif prop.kind == COVER:
            prop_text = f"{active} && {cond}" if active else cond
        else:  # pragma: no cover - every kind is handled above
            raise ValueError(f"property kind {prop.kind} has no concurrent form")
        label = fresh_name(f"sva_{pid}")
        comment = f"// {pid} ({prop.kind}): {prop.condition_key} {' '.join(prop.condition.split())}"
        if prop.trigger is not None:
            comment += f", when {' '.join(prop.trigger.split())}"
        if f:
            comment += f", from_step {f}"
        if prop.kind == COVER:
            statement = (
                f"{label}: cover property ({clocking}\n    {prop_text})\n"
                f'    $display("SVA_COVER {pid} row %0d", $sampled({row_counter}));'
            )
        else:
            statement = (
                f"{label}: assert property ({clocking}\n    {prop_text})\n"
                f'    else $error("SVA_FAIL {pid} row %0d", $sampled({row_counter}));'
            )
        code.monitors += [comment, *statement.split("\n"), ""]
    return code
