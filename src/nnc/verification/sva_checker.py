"""SystemVerilog checker and bind-file emission for the SVA backend."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

from ..parser.ast import BooleanExpression
from ..transformers.verilog.generation.observation import (
    IMPORT_INPUT,
    INPUT_PORT,
    ObservedSignal,
    VerilogObservation,
)
from .placeholders import TextSegment
from .references import CONSTANT
from .sva import CONCURRENT, SvaSelection
from .sva_concurrent import emit_concurrent
from .sva_formal import InputAssumption
from .sva_monitors import LIVE, REPLAY_TASK, REPORT_TASK, emit_monitors


class ConditionRenderer(Protocol):
    """Renders property conditions with the encodings of the generated RTL."""

    def render(self, condition: BooleanExpression, names: Mapping[str, str]) -> str:
        """Return the checker expression of a condition."""
        ...

    def declarations(self) -> str:
        """Return the literal parameters and helpers the conditions use."""
        ...

    def declared_names(self) -> set[str]:
        """Return the names ``declarations`` declares."""
        ...


@dataclass(frozen=True, slots=True)
class SvaCheckerFiles:
    """Generated checker files.

    Args:
        checker: Checker module text.
        bind: Bind-module text, or ``None`` when formal output is not requested.
        control_bits: State bits of the property monitors (counters, pending
            vectors, flags), without input copies and simulation-only result
            diagnostics.
        ports: Checker ports besides clock and reset, in declaration order;
            each is named after the RTL signal it reads.
        live: Liveness helper module text (``<module>_sva_live``), or ``None``
            when the formal checks have no liveness property.
    """

    checker: str
    bind: str | None
    control_bits: int = 0
    ports: tuple[str, ...] = ()
    live: str | None = None


def emit_checker_files(
    observation: VerilogObservation,
    selection: SvaSelection,
    encode_value: Callable[[float, ObservedSignal], str],
    encode_constant: Callable[[float], str],
    renderer: ConditionRenderer,
    assumptions: tuple[InputAssumption, ...] = (),
) -> SvaCheckerFiles:
    """Emit the checker and optional bind file for one root module.

    ``assumptions`` (formal modes) constrain live root input ports; those
    ports are added to the checker interface.
    """
    required = _required_signals(selection)
    read = _unique_ports(required)
    ports = dict(read)
    for assumption in assumptions:
        ports.setdefault(assumption.signal.expression, assumption.signal)
    used = {observation.clock, observation.reset, *ports, *_RESERVED}
    input_copies = _input_copies(required, used)
    references = {
        name: input_copies.get(name, (signal.expression, signal))[0]
        for name, signal in required.items()
    }

    checker, control_bits, has_live = _emit_checker(
        observation,
        selection,
        ports,
        input_copies,
        references,
        used,
        encode_value,
        encode_constant,
        renderer,
        assumptions,
    )
    bind = (
        _emit_bind(observation, selection, ports) if selection.options.formal else None
    )
    return SvaCheckerFiles(
        checker=checker,
        bind=bind,
        control_bits=control_bits,
        ports=tuple(ports),
        live=_emit_live_helper(observation, selection) if has_live else None,
    )


# Names the checker declares itself; an RTL signal with one of these names is
# rejected (see _emit_checker), and generated names avoid them.
_RESERVED = (REPORT_TASK, REPLAY_TASK)


def _required_signals(selection: SvaSelection) -> dict[str, ObservedSignal]:
    """Return selected signals in first-use order."""
    required: dict[str, ObservedSignal] = {}
    for prop in selection.properties:
        for name, signal in prop.signals.items():
            required.setdefault(name, signal)
    for raw in selection.raw:
        for name, signal in raw.signals.items():
            required.setdefault(name, signal)
    return required


def _unique_ports(
    required: dict[str, ObservedSignal],
) -> dict[str, ObservedSignal]:
    """Deduplicate checker ports by their RTL expression."""
    ports: dict[str, ObservedSignal] = {}
    for signal in required.values():
        ports.setdefault(signal.expression, signal)
    return ports


def _input_copies(
    required: dict[str, ObservedSignal],
    used: set[str],
) -> dict[str, tuple[str, ObservedSignal]]:
    """Map selected root and imported inputs to row-aligned copy names.

    Copies are keyed by TENNCell name, not RTL expression: a root input and an
    imported input may share a wire but have different initial values at row 0.
    """
    copies: dict[str, tuple[str, ObservedSignal]] = {}
    for name, signal in required.items():
        if signal.kind not in (INPUT_PORT, IMPORT_INPUT):
            continue
        fragment = signal.expression if signal.kind == INPUT_PORT else name
        base = f"sva_input_{_identifier_fragment(fragment)}"
        copies[name] = (_fresh_name(base, used), signal)
    return copies


def _fresh_name(base: str, used: set[str]) -> str:
    """Return and reserve a unique SystemVerilog identifier."""
    name = base
    suffix = 2
    while name in used:
        name = f"{base}_{suffix}"
        suffix += 1
    used.add(name)
    return name


def _identifier_fragment(text: str) -> str:
    """Turn an RTL identifier into a safe generated-name fragment."""
    return re.sub(r"[^A-Za-z0-9_$]", "_", text)


def _decl(signal: ObservedSignal, name: str, *, direction: str = "") -> str:
    """Render one checker signal declaration."""
    prefix = f"{direction} " if direction else ""
    signed = " signed" if signal.signed and signal.width > 1 else ""
    width = "" if signal.width == 1 else f" [{signal.width - 1}:0]"
    return f"{prefix}logic{signed}{width} {name}"


def options_comment(selection: SvaSelection) -> str:
    """Return the comment line recording the generation options, which
    starts every SVA-specific file."""
    options = selection.options
    return (
        "// Generated by nnc-gen -t sva: "
        f"mode={options.mode}, style={options.style}, "
        f"depth={options.effective_depth}, max_bound={options.effective_max_bound}"
    )


def _emit_checker(
    observation: VerilogObservation,
    selection: SvaSelection,
    ports: dict[str, ObservedSignal],
    input_copies: dict[str, tuple[str, ObservedSignal]],
    references: dict[str, str],
    used: set[str],
    encode_value: Callable[[float, ObservedSignal], str],
    encode_constant: Callable[[float], str],
    renderer: ConditionRenderer,
    assumptions: tuple[InputAssumption, ...],
) -> tuple[str, int, bool]:
    """Emit one checker module (monitor or concurrent style), its monitor
    state size and whether its formal checks include liveness."""
    row_counter = _fresh_name("sva_row", used)
    monitored = selection.properties
    conditions = {
        item.bound.property.id: renderer.render(item.bound.condition, references)
        for item in monitored
    }
    triggers = {
        item.bound.property.id: renderer.render(item.bound.trigger, references)
        for item in monitored
        if item.bound.trigger is not None
    }
    # Declarations first: building a conversion helper can add a literal.
    declarations = renderer.declarations()
    concurrent = selection.options.style == CONCURRENT
    reports = bool(monitored) and not concurrent
    declared = renderer.declared_names() | (
        {REPORT_TASK, REPLAY_TASK} if reports else set()
    )
    clashes = sorted(declared & {observation.clock, observation.reset, *ports})
    if clashes:
        raise ValueError(
            "RTL signals read by the SVA checker have names the checker declares "
            f"itself: {', '.join(clashes)}; rename them (for a port, with rename)"
        )
    if concurrent:
        monitors = emit_concurrent(
            monitored,
            conditions,
            triggers,
            observation.clock,
            observation.reset,
            observation.reset_active_high,
            row_counter,
            lambda base: _fresh_name(base, used),
        )
    else:
        monitors = emit_monitors(
            monitored,
            conditions,
            triggers,
            selection.trace_semantics == "weak",
            observation.clock,
            observation.reset,
            observation.reset_active_high,
            row_counter,
            lambda base: _fresh_name(base, used),
        )

    interface = [
        f"input logic {observation.clock}",
        f"input logic {observation.reset}",
        *[
            _decl(signal, expression, direction="input")
            for expression, signal in ports.items()
        ],
    ]
    lines = [options_comment(selection), "`default_nettype none", ""]
    lines.append(f"module {observation.module_name}_sva (")
    for index, declaration in enumerate(interface):
        suffix = "," if index < len(interface) - 1 else ""
        lines.append(f"    {declaration}{suffix}")
    lines.extend([");", ""])

    if declarations:
        lines.extend(declarations.rstrip("\n").splitlines())
        lines.append("")

    for copy_name, signal in input_copies.values():
        lines.append(f"{_decl(signal, copy_name)};")
    if input_copies:
        lines.append("")

    reset_edge = "posedge" if observation.reset_active_high else "negedge"
    reset_condition = (
        observation.reset if observation.reset_active_high else f"!{observation.reset}"
    )
    if input_copies:
        lines.append(
            f"always_ff @(posedge {observation.clock} or {reset_edge} {observation.reset}) begin"
        )
        lines.append(f"    if ({reset_condition}) begin")
        for copy_name, signal in input_copies.values():
            assert signal.initial_value is not None
            lines.append(
                f"        {copy_name} <= {encode_value(signal.initial_value, signal)};"
            )
        lines.append("    end else begin")
        for copy_name, signal in input_copies.values():
            lines.append(f"        {copy_name} <= {signal.expression};")
        lines.extend(["    end", "end", ""])

    lines.extend(monitors.step_counter)
    lines.extend(
        [
            "`ifndef FORMAL",
            f"logic [63:0] {row_counter};",
            f"always_ff @(posedge {observation.clock} or {reset_edge} {observation.reset}) begin",
            f"    if ({reset_condition}) begin",
            f"        {row_counter} <= 64'd0;",
            "    end else begin",
            f"        {row_counter} <= {row_counter} + 64'd1;",
            "    end",
            "end",
            "`endif",
            "",
        ]
    )
    lines.extend(monitors.monitors)
    if reports:
        lines.append("`ifndef FORMAL")
        lines.extend(monitors.recorders)
        lines.extend(monitors.report)
        lines.append("")
        lines.extend(monitors.replay)
        lines.extend(["`endif", ""])
    formal = selection.options.formal and not concurrent
    if formal:
        lines.extend(
            _formal_block(
                observation,
                monitors.formal_checks,
                monitors.formal_invariants,
                assumptions,
                lambda base: _fresh_name(base, used),
            )
        )

    for raw in selection.raw:
        lines.append(f"// raw sva: {raw.bound.entry.id}")
        rendered: list[str] = []
        for segment in raw.bound.segments:
            if isinstance(segment, TextSegment):
                rendered.append(segment.text)
            elif segment.kind == CONSTANT:
                assert segment.value is not None
                rendered.append(encode_constant(segment.value))
            else:
                rendered.append(references[segment.target])
        lines.extend("".join(rendered).splitlines())
        lines.append(f"// end raw sva: {raw.bound.entry.id}")
        lines.append("")

    lines.extend(["endmodule", "", "`default_nettype wire", ""])
    has_live = formal and any(kind == LIVE for _, kind, _ in monitors.formal_checks)
    return "\n".join(lines), monitors.control_bits, has_live


def _formal_block(
    observation: VerilogObservation,
    checks: list[tuple[str, str, str]],
    invariants: list[tuple[str, str]],
    assumptions: tuple[InputAssumption, ...],
    fresh_name: Callable[[str], str],
) -> list[str]:
    """Formal-only statements (``ifdef FORMAL``): reset scheme, input
    assumptions, one labelled assertion, cover or liveness check per
    property, and the monitor-state invariants (for induction proofs)."""
    clock, reset = observation.clock, observation.reset
    started = fresh_name("sva_formal_reset")
    active = reset if observation.reset_active_high else f"!{reset}"
    lines = [
        "`ifdef FORMAL",
        "// Formal checks. The reset is active in the initial state, applied at",
        "// the first edge and never again, so row 0 is the first edge after it.",
        f"logic {started} = 1'b1;",
        f"always @(posedge {clock}) {started} <= 1'b0;",
        f"always @(*) assume ({active} == {started});",
    ]
    for assumption in assumptions:
        port = assumption.signal.expression
        lines.append(
            f"// verification.environment.{assumption.name}.range on the live input"
        )
        lines.append(
            f"always @(*) assume ({port} >= {assumption.literal(assumption.low)} && "
            f"{port} <= {assumption.literal(assumption.high)});"
        )
    live = [(pid, signal) for pid, kind, signal in checks if kind == LIVE]
    if live:
        # One $live cell for all of them (suprove checks only the first
        # liveness property of a model): once out of reset, every property
        # must eventually be satisfied. Each flag is sticky, so their
        # conjunction eventually holds exactly when each one does.
        lines.append(f"// liveness: {', '.join(pid for pid, _ in live)}")
        satisfied = " && ".join(f"({signal})" for _, signal in live)
        lines.append(
            f"{observation.module_name}_sva_live {fresh_name('sva_liveness')} "
            f"(.a({satisfied}), .en(!({active})));"
        )
    safety = [check for check in checks if check[1] != LIVE]
    if safety or invariants:
        lines.append(f"always @(posedge {clock}) begin")
        lines.append(f"    if (!({active})) begin")
        for pid, kind, signal in safety:
            label = fresh_name(f"sva_{pid}_{'check' if kind == 'assert' else 'cover'}")
            statement = (
                f"assert (!{signal})" if kind == "assert" else f"cover ({signal})"
            )
            lines.append(f"        {label}: {statement};")
        for base, expression in invariants:
            lines.append(f"        {fresh_name(base)}: assert ({expression});")
        lines += ["    end", "end"]
    lines += ["`endif", ""]
    return lines


def _emit_live_helper(observation: VerilogObservation, selection: SvaSelection) -> str:
    """Emit the liveness helper module: a Yosys ``$live`` cell, which the
    yosys-slang front end cannot express, read with ``read_verilog -icells``."""
    return "\n".join(
        [
            options_comment(selection),
            "// Liveness helper for formal checks (Yosys only: read_verilog -formal",
            "// -icells). Whenever en is true, a must eventually be true.",
            f"module {observation.module_name}_sva_live (input wire a, input wire en);",
            "    \\$live live (.A(a), .EN(en));",
            "endmodule",
            "",
        ]
    )


def _emit_bind(
    observation: VerilogObservation,
    selection: SvaSelection,
    ports: dict[str, ObservedSignal],
) -> str:
    """Emit a bind statement connecting the checker in the DUT scope."""
    connections = [observation.clock, observation.reset, *ports]
    lines = [options_comment(selection), "`default_nettype none", ""]
    lines.append(
        f"bind {observation.module_name} {observation.module_name}_sva "
        f"{observation.module_name}_sva_inst ("
    )
    for index, name in enumerate(connections):
        suffix = "," if index < len(connections) - 1 else ""
        lines.append(f"    .{name}({name}){suffix}")
    lines.extend([");", "", "`default_nettype wire", ""])
    return "\n".join(lines)
