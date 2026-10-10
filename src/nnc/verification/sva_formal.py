"""Formal checks of the SVA backend (SymbiYosys): input assumptions and ``.sby``.

Formal reads the RTL, the checker and the bind file with the yosys-slang
front end (``read_slang``, which supports ``bind``; the built-in Verilog front
end ignores it), then ``prep`` and ``async2sync``. Step 0 is the reset step;
row ``j`` is checked at engine step ``j + 2``, because an immediate assertion
inside ``always @(posedge clk)`` reports one step after the values it samples.
So ``--sva-depth D`` (rows ``0..D-1``) is engine depth ``D + 2``.

Four tasks: ``bmc`` and ``cover`` explore rows ``0..D-1``; ``prove_kind``
(k-induction, ``smtbmc``, induction length ``D + 2``) and ``prove_pdr``
(``abc pdr``) prove all assertions for runs of any length. A proof covers every
assertion at once: one false property makes both fail, and ``bmc`` names it.
k-induction may answer UNKNOWN for a true property when the induction length
is shorter than the history a monitor keeps (the largest ``after``/``within``
bound); PDR has no such limit. Only PASS means proved.

Unbounded ``eventually`` is liveness: one ``$live`` cell for all such
properties (their sticky flags in conjunction; ``suprove`` checks only the
first liveness property of a model) in a helper module
(``read_verilog -icells``; slang cannot express it), checked by a fifth task,
``live`` (``aiger suprove``), only generated when needed. SymbiYosys turns the
assertions into assumptions in live mode, which would make a failing safety
property hide a liveness failure, so the ``live`` task removes them first; the
other tasks drop the ``$live`` cells.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..transformers.verilog.generation.observation import (
    INPUT_PORT,
    ObservedSignal,
    VerilogObservation,
)
from .generic_properties.native import VerificationError

if TYPE_CHECKING:
    from .config import InputEnvironment

# Engine steps before property row 0 is reported (reset step + clocked check).
DEPTH_OFFSET = 2


@dataclass(frozen=True, slots=True)
class InputAssumption:
    """Encoded bounds assumed on a live root input port.

    Args:
        name: TENNCell input name.
        signal: The input port as observed in the RTL.
        low: Smallest encoded value.
        high: Largest encoded value.
    """

    name: str
    signal: ObservedSignal
    low: int
    high: int

    def literal(self, value: int) -> str:
        """Return a sized literal in the port's signedness."""
        if self.signal.signed:
            sign = "-" if value < 0 else ""
            return f"{sign}{self.signal.width}'sd{abs(value)}"
        return f"{self.signal.width}'d{value}"


def input_assumptions(
    environment: Mapping[str, InputEnvironment],
    observation: VerilogObservation,
) -> tuple[tuple[InputAssumption, ...], tuple[str, ...]]:
    """Encode the ``environment`` ranges of root inputs for their ports.

    Bounds are rounded inward (``ceil`` of the low, ``floor`` of the high
    encoded value; fixed point is scaled by ``2**frac_bits`` first) and
    intersected with the port's representable range.

    Returns:
        The assumptions and warnings for ranges clipped to the port.

    Raises:
        VerificationError: For a range that is not finite, an input that is
            not an RTL port, or a range with no representable value.
    """
    assumptions = []
    warnings = []
    for name, entry in environment.items():
        if entry.range is None:
            continue
        low, high = entry.range
        if not (math.isfinite(low) and math.isfinite(high)):
            raise VerificationError(
                f"verification.environment.{name}.range must be finite for formal checks"
            )
        signal = observation.signals[name]
        if signal.kind != INPUT_PORT:
            raise VerificationError(
                f"verification.environment.{name}: the input is not a port of the "
                "generated RTL (it comes from an external module), so formal checks "
                "cannot constrain it"
            )
        scale = 2**signal.frac_bits if signal.encoding_kind == "fixed" else 1
        if signal.signed:
            port_low, port_high = (
                -(2 ** (signal.width - 1)),
                2 ** (signal.width - 1) - 1,
            )
        else:
            port_low, port_high = 0, 2**signal.width - 1
        # Clamp the scaled bounds (which may overflow to infinity for huge
        # finite ranges) just outside the port range before rounding inward.
        low_s = min(max(low * scale, port_low - 1), port_high + 1)
        high_s = min(max(high * scale, port_low - 1), port_high + 1)
        clipped_low = max(math.ceil(low_s), port_low)
        clipped_high = min(math.floor(high_s), port_high)
        if clipped_low > clipped_high:
            raise VerificationError(
                f"verification.environment.{name}.range [{low:g}, {high:g}] has no "
                f"value representable on port '{signal.expression}'"
            )
        if math.ceil(low_s) < port_low or math.floor(high_s) > port_high:
            warnings.append(
                f"verification.environment.{name}.range [{low:g}, {high:g}] is clipped "
                f"to the values port '{signal.expression}' can hold"
            )
        assumptions.append(InputAssumption(name, signal, clipped_low, clipped_high))
    return tuple(assumptions), tuple(warnings)


def sby_text(
    header: str,
    module: str,
    depth_rows: int,
    files: Sequence[str],
    live: str | None = None,
) -> str:
    """Return the SymbiYosys file with the ``bmc``, ``cover``, ``prove_kind``
    and ``prove_pdr`` tasks, and ``live`` when there is a liveness helper.

    Args:
        header: Options comment (``//`` is turned into ``#``).
        module: Root RTL module (the formal top; the checker is bound in it).
        depth_rows: Rows ``0..depth_rows-1`` are explored.
        files: Source paths relative to the ``.sby`` file, in reading order.
        live: File name of the liveness helper module, or ``None``.
    """
    names = [path.rsplit("/", 1)[-1] for path in files]  # [files] copies by name
    depth = depth_rows + DEPTH_OFFSET
    lines = [
        "#" + header.removeprefix("//"),
        f"# Formal checks of {module}: rows 0..{depth_rows - 1} after reset. Engine",
        f"# depth {depth} = rows + {DEPTH_OFFSET} (the reset step, and clocked assertions",
        "# report one step after the row they check). prove_kind (k-induction,",
        f"# induction length {depth}) and prove_pdr prove all assertions for runs of",
        "# any length; only PASS means proved. Run: sby -f <this file> [task]",
    ]
    if live is not None:
        lines += [
            "# live proves the unbounded eventually properties on infinite runs, with",
            "# the other assertions removed (SymbiYosys would assume them); it needs",
            "# the suprove engine (oss-cad-suite for Linux). Without suprove, name the",
            "# other tasks: sby -f <this file> bmc (cover, prove_kind, prove_pdr).",
        ]
    lines += [
        "[tasks]",
        "bmc",
        "cover",
        "prove_kind",
        "prove_pdr",
        *(["live"] if live is not None else []),
        "",
        "[options]",
        "bmc: mode bmc",
        "cover: mode cover",
        "prove_kind: mode prove",
        "prove_pdr: mode prove",
        *(["live: mode live"] if live is not None else []),
        # The live task has no depth (SymbiYosys rejects one there).
        f"{'~live: ' if live is not None else ''}depth {depth}",
        "multiclock off",
        "",
        "[engines]",
        "bmc: smtbmc",
        "cover: smtbmc",
        "prove_kind: smtbmc",
        "prove_pdr: abc pdr",
        *(["live: aiger suprove"] if live is not None else []),
        "",
        "[script]",
        "plugin -i slang",
        *([f"read_verilog -formal -icells {live}"] if live is not None else []),
        f"read_slang -D FORMAL {' '.join(names)} --top {module}",
        f"prep -top {module}",
        "async2sync",
        *(["live: chformal -assert -remove"] if live is not None else []),
        "",
        "[files]",
        *files,
        *([live] if live is not None else []),
        "",
    ]
    return "\n".join(lines)
