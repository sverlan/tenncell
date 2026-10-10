"""Read a SymbiYosys witness (``.yw``) as SVA simulation stimulus.

A Yosys witness trace lists signal fragments (a path, a width, and the
``offset`` of the fragment's lowest bit within the signal) and, per engine
step, a ``bits`` string: the step's fragments from the last listed one to the
first, each most significant bit first. Fragments marked ``init_only`` appear
in step 0 only. A port may be split into several fragments.

With the reset scheme of the generated formal checks, step 0 is the reset
step, and the input values of step ``k`` (``k >= 1``) drive the step that
produces row ``k``. A bmc or cover trace ends two steps after the row where it
fails or hits (the clocked check reports one step late), so a witness with
``n`` steps covers rows ``0..n-3``.

Input bits the solver left unconstrained (``x`` or ``?``) are replayed as 0;
reset bits must be 0 or 1.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .generic_properties.native import VerificationError

# Engine steps that are not rows: the reset step, and the step after the last
# row (the clocked check reports one step late).
_EXTRA_STEPS = 3
_UNKNOWN = "x?"


@dataclass(frozen=True, slots=True)
class WitnessPort:
    """One top-level port read from a witness.

    Args:
        name: Port name.
        width: Port width.
        signed: Whether values are two's complement.
    """

    name: str
    width: int
    signed: bool


@dataclass(frozen=True, slots=True)
class WitnessReplay:
    """Rows of a witness to replay.

    Args:
        rows: Number of rows after row 0 (``steps`` of the simulation); the
            witness's violation or cover is on the last row.
        records: Port values (encoded integers) of each record ``1..rows``,
            keyed by port name.
    """

    rows: int
    records: tuple[dict[str, int], ...]


@dataclass(frozen=True, slots=True)
class _Fragment:
    name: str | None  # top-level port name, None for internal signals
    width: int
    offset: int
    init_only: bool


def read_witness(
    path: Path,
    ports: Sequence[WitnessPort],
    reset: str,
    reset_active_high: bool,
) -> WitnessReplay:
    """Read the input records of a witness of the generated formal checks.

    Args:
        path: Yosys witness file written by SymbiYosys (``trace.yw``).
        ports: Root input ports of the model (may be empty).
        reset: Reset port name.
        reset_active_high: Whether the reset is active high.

    Returns:
        The number of rows and the encoded input values of each record.

    Raises:
        VerificationError: If the file is not a well-formed Yosys witness,
            lacks a port, is too short, has an unknown reset bit, or does not
            start from the reset (reset active at step 0 and inactive after;
            an induction trace starts from an arbitrary state).
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise VerificationError(f"{path}: cannot read the witness: {error}") from error
    if not isinstance(data, dict) or data.get("format") != "Yosys Witness Trace":
        raise VerificationError(f"{path}: not a Yosys witness trace (.yw)")
    fragments = _fragments(path, data.get("signals"))
    steps = _steps(path, data.get("steps"), fragments)
    if len(steps) < _EXTRA_STEPS:
        raise VerificationError(
            f"{path}: the witness has {len(steps)} steps; a bmc or cover trace of "
            f"the generated checks has at least {_EXTRA_STEPS}"
        )
    for name, width in [(reset, 1), *((port.name, port.width) for port in ports)]:
        found = _width(fragments, name)
        if found is None:
            raise VerificationError(f"{path}: the witness has no signal '{name}'")
        if found != width:
            raise VerificationError(
                f"{path}: signal '{name}' has {found} bits in the witness, the port "
                f"has {width}"
            )

    active = "1" if reset_active_high else "0"
    for index, bits in enumerate(steps):
        level = _bits(fragments, bits, index, reset)
        if level in _UNKNOWN:
            raise VerificationError(
                f"{path}: the reset is unknown at step {index} of the witness"
            )
        if (level == active) != (index == 0):
            raise VerificationError(
                f"{path}: the witness does not start from the reset (reset active "
                "at step 0, inactive after): replay bmc or cover traces, not "
                "induction traces"
            )

    rows = len(steps) - _EXTRA_STEPS
    records = []
    for index in range(1, rows + 1):
        record = {}
        for port in ports:
            text = _bits(fragments, steps[index], index, port.name)
            number = int("".join("0" if c in _UNKNOWN else c for c in text), 2)
            if port.signed and number >= 1 << (port.width - 1):
                number -= 1 << port.width
            record[port.name] = number
        records.append(record)
    return WitnessReplay(rows=rows, records=tuple(records))


def _fragments(path: Path, signals: object) -> list[_Fragment]:
    if not isinstance(signals, list):
        raise VerificationError(f"{path}: the witness has no signal list")
    fragments = []
    for signal in signals:
        fragment = _fragment(signal)
        if fragment is None:
            raise VerificationError(f"{path}: malformed witness signal {signal!r}")
        fragments.append(fragment)
    return fragments


def _fragment(signal: object) -> _Fragment | None:
    """One signal fragment, or ``None`` if its JSON types are wrong."""
    if not isinstance(signal, dict):
        return None
    parts = signal.get("path")
    width = signal.get("width")
    offset = signal.get("offset", 0)
    init_only = signal.get("init_only", False)
    if not (
        isinstance(parts, list)
        and parts
        and all(isinstance(part, str) for part in parts)
    ):
        return None
    if isinstance(width, bool) or not isinstance(width, int) or width <= 0:
        return None
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        return None
    if not isinstance(init_only, bool):
        return None
    name = parts[0].removeprefix("\\") if len(parts) == 1 else None
    return _Fragment(name, width, offset, init_only)


def _listed(fragments: list[_Fragment], step: int) -> list[_Fragment]:
    return [f for f in fragments if step == 0 or not f.init_only]


def _steps(path: Path, steps: object, fragments: list[_Fragment]) -> list[str]:
    if not isinstance(steps, list):
        raise VerificationError(f"{path}: the witness has no step list")
    result = []
    for index, step in enumerate(steps):
        bits = step.get("bits") if isinstance(step, dict) else None
        expected = sum(f.width for f in _listed(fragments, index))
        if not isinstance(bits, str) or len(bits) != expected:
            raise VerificationError(
                f"{path}: step {index} of the witness should have {expected} bits"
            )
        if any(char not in "01" + _UNKNOWN for char in bits):
            raise VerificationError(
                f"{path}: step {index} of the witness has bits other than 0, 1, x, ?"
            )
        result.append(bits)
    return result


def _width(fragments: list[_Fragment], name: str) -> int | None:
    """Width of a top-level signal assembled from its fragments."""
    own = [f for f in fragments if f.name == name and not f.init_only]
    if not own:
        return None
    covered = sorted((f.offset, f.offset + f.width) for f in own)
    position = 0
    for start, stop in covered:
        if start != position:
            return None  # a gap or an overlap: not a complete signal
        position = stop
    return position


def _bits(fragments: list[_Fragment], bits: str, step: int, name: str) -> str:
    """Bits (MSB first) of a top-level signal in one step."""
    listed = _listed(fragments, step)
    total = len(bits)
    pieces: dict[int, str] = {}
    position = 0  # taken from the end: the first fragment is last
    for fragment in listed:
        start = total - position - fragment.width
        if fragment.name == name and not fragment.init_only:
            pieces[fragment.offset] = bits[start : start + fragment.width]
        position += fragment.width
    # Highest offset first, so the result is MSB first.
    return "".join(pieces[offset] for offset in sorted(pieces, reverse=True))
