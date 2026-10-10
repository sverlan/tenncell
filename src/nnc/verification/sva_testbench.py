"""Simulation testbench for the SVA checker (``<stem>_tb.sv``).

The testbench instantiates the generated RTL and its checker side by side and
connects the checker by hierarchical names (simulators such as Icarus do not
support ``bind``). Event schedule:

- the reset is active from time 0, applied at the first rising edge and
  released at the next falling edge;
- record ``k`` (``k = 1..N``) is driven at the falling edge before sampling
  edge ``k - 1`` and drives the transition from row ``k - 1`` to row ``k`` at
  that edge; sampling edge ``j`` (``j = 0..N``) sees row ``j`` (the registers
  before the edge, and, through the checker's copies, the record of row ``j``);
- after edge ``N``, at the falling edge, the checker's ``sva_report`` prints
  the results, then the simulation ends with ``$fatal`` when a generic
  property failed, and with ``$finish`` otherwise.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .sva_monitors import REPLAY_TASK, REPORT_TASK
from .sva_stimulus import SvaStimulus

# Half the clock period, in time units of the `timescale` (1 ns).
HALF_PERIOD = 5


@dataclass(frozen=True, slots=True)
class BenchPort:
    """One port of the generated root module.

    Args:
        name: Port name.
        direction: ``input`` or ``output``.
        width: Bit width.
        signed: Whether the port is declared signed.
    """

    name: str
    direction: str
    width: int
    signed: bool


def emit_testbench(
    module: str,
    checker_module: str,
    clock: str,
    reset: str,
    reset_active_high: bool,
    ports: Sequence[BenchPort],
    checker_ports: Sequence[str],
    stimulus: SvaStimulus,
    hex_file: str,
    has_report: bool,
    header: str,
) -> str:
    """Return the testbench text.

    Args:
        module: Name of the generated RTL module.
        checker_module: Name of its checker module.
        clock: Clock port.
        reset: Reset port.
        reset_active_high: Whether the reset is active high.
        ports: Ports of the RTL module, clock and reset included.
        checker_ports: Checker ports besides clock and reset; each is the name
            of the RTL signal it reads.
        stimulus: Encoded stimulus (``steps`` records or steps).
        hex_file: Default stimulus file name (overridable with ``+stimulus=``).
        has_report: Whether the checker has a report task (generic properties).
        header: Comment line recording the generation options.
    """
    used = {port.name for port in ports} | {module, checker_module}
    names = _Names(used)
    stim, index, failed, path = (
        names.new("sva_stim"),
        names.new("sva_k"),
        names.new("sva_failed"),
        names.new("sva_stimulus_file"),
    )
    reproduced = names.new("sva_reproduced")
    checker = names.new("sva_checker")
    dut = names.new("dut")
    records_param, inputs_param = names.new("RECORDS"), names.new("INPUTS")
    active, inactive = ("1'b1", "1'b0") if reset_active_high else ("1'b0", "1'b1")
    initial = {
        port.port: value for port, value in zip(stimulus.ports, stimulus.initial)
    }
    driven = {port.port: port for port in stimulus.ports}
    records = stimulus.steps
    uses_file = bool(stimulus.ports) and records > 0

    lines = [header]
    if stimulus.note:
        lines.append(f"// {stimulus.note}")
    if stimulus.ports:
        order = ", ".join(f"{p.name} -> {p.port}" for p in stimulus.ports)
        lines += [
            f"// Testbench for {module}: {records} input records from {hex_file}",
            f"// (inputs in this order: {order}). Run it from the output directory,",
            f"// or pass +stimulus=<path of {hex_file}>.",
        ]
    else:
        lines.append(f"// Testbench for {module}: {records} steps.")
    lines += ["`timescale 1ns/1ps", "`default_nettype none", "", f"module {module}_tb;"]
    lines.append(f"    localparam int {records_param} = {records};")
    if uses_file:
        lines.append(f"    localparam int {inputs_param} = {len(stimulus.ports)};")
    lines.append("")
    for port in ports:
        decl = _decl(port)
        if port.name == clock:
            lines.append(f"    {decl} = 1'b0;")
        elif port.name == reset:
            lines.append(f"    {decl} = {active};")
        elif port.name in initial:
            value = driven[port.name].literal(initial[port.name])
            lines.append(f"    {decl} = {value};  // initial value")
        else:
            lines.append(f"    {decl};")
    if uses_file:
        word = max(port.width for port in stimulus.ports)
        lines.append(
            f"    logic [{word - 1}:0] {stim} [0:{records_param}*{inputs_param}-1];"
        )
    lines.append("")

    lines += _instance(module, dut, [(p.name, p.name) for p in ports])
    lines.append("")
    connections = [(clock, clock), (reset, reset)] + [
        (name, f"{dut}.{name}") for name in checker_ports
    ]
    lines += _instance(checker_module, checker, connections)
    lines += [
        "",
        f"    always #{HALF_PERIOD} {clock} = ~{clock};",
        "",
        "    initial begin",
    ]
    replay_row = stimulus.replay_row
    if has_report:
        lines.append(f"        bit {failed};")
    if has_report and replay_row is not None:
        lines.append(f"        bit {reproduced};")
    if uses_file:
        lines += [
            f"        string {path};",
            f'        if (!$value$plusargs("stimulus=%s", {path})) {path} = "{hex_file}";',
            f"        $readmemh({path}, {stim});",
        ]
    lines += [
        "        // Reset: applied at the first rising edge, released here.",
        f"        @(negedge {clock});",
        f"        {reset} = {inactive};",
    ]
    if records > 0:
        lines += [
            "        // Record k drives the transition from row k-1 to row k.",
            f"        for (int {index} = 0; {index} < {records_param}; {index}++) begin",
        ]
        for position, driven_port in enumerate(stimulus.ports):
            lines.append(
                f"            {driven_port.port} = "
                f"{stim}[{index}*{inputs_param} + {position}][{driven_port.width - 1}:0];"
            )
        lines += [f"            @(negedge {clock});", "        end"]
    lines += [
        "        // The last sampling edge has seen the last row.",
        f"        @(negedge {clock});",
    ]
    if has_report and replay_row is not None:
        # A replay succeeds when the witness's failure or cover comes back.
        lines += [
            f"        {checker}.{REPORT_TASK}({failed});",
            f"        {checker}.{REPLAY_TASK}(64'd{replay_row}, {reproduced});",
            f"        if ({reproduced})",
            f'            $display("SVA_REPLAY reproduced on row {replay_row}");',
            "        else",
            '            $fatal(1, "SVA_REPLAY NOT reproduced: no property first '
            f'failed and no cover was first hit on row {replay_row}");',
        ]
    elif has_report:
        lines += [
            f"        {checker}.{REPORT_TASK}({failed});",
            f'        if ({failed}) $fatal(1, "SVA: a generic property failed");',
        ]
    lines += [
        "        $finish;",
        "    end",
        "endmodule",
        "",
        "`default_nettype wire",
        "",
    ]
    return "\n".join(lines)


def _decl(port: BenchPort) -> str:
    signed = " signed" if port.signed and port.width > 1 else ""
    width = "" if port.width == 1 else f" [{port.width - 1}:0]"
    return f"logic{signed}{width} {port.name}"


def _instance(module: str, name: str, connections: list[tuple[str, str]]) -> list[str]:
    lines = [f"    {module} {name} ("]
    for position, (port, signal) in enumerate(connections):
        suffix = "," if position < len(connections) - 1 else ""
        lines.append(f"        .{port}({signal}){suffix}")
    lines.append("    );")
    return lines


class _Names:
    """Testbench identifiers that avoid the port and module names."""

    def __init__(self, used: set[str]):
        self.used = set(used)

    def new(self, base: str) -> str:
        name, suffix = base, 2
        while name in self.used:
            name = f"{base}_{suffix}"
            suffix += 1
        self.used.add(name)
        return name
