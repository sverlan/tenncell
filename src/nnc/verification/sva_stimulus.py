"""Stimulus for SVA simulation: input records encoded for the RTL ports.

The values are encoded in Python, exactly as the RTL encodes constants
(``round(value * 2**frac_bits)`` for fixed point, ``round(value)`` for logic).
The encoded words go to ``<stem>_inputs.hex`` (``$readmemh``); the same words
decoded back to reals go to ``<stem>_inputs_decoded.csv``, which ``nnc-verify
--inputs`` checks, so the two checkers see the same quantized inputs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ..transformers.verilog.generation.observation import (
    INPUT_PORT,
    VerilogObservation,
)
from .generic_properties.native import VerificationError
from .records import read_input_records
from .sva_replay import WitnessPort, read_witness

if TYPE_CHECKING:
    from ..model.system import NncSystem
    from .config import VerificationConfig


@dataclass(frozen=True, slots=True)
class SvaStimulusSource:
    """Where the simulation stimulus comes from (``--sva-inputs``,
    ``--sva-steps`` or ``--sva-replay``; exactly one in simulation).

    Args:
        inputs: Input file (models with inputs), read like ``nnc-verify --inputs``.
        steps: Number of steps (models without inputs).
        delimiter: Field delimiter of ``inputs``; ``" "`` means any whitespace.
        skip_lines: Lines skipped before the header of ``inputs``.
        witness: SymbiYosys witness (``.yw``) of a bmc or cover trace of the
            generated formal checks, replayed up to the row where it fails
            or hits (any model).
    """

    inputs: Path | None = None
    steps: int | None = None
    delimiter: str = ","
    skip_lines: int = 0
    witness: Path | None = None


@dataclass(frozen=True, slots=True)
class StimulusPort:
    """One root input and the RTL port that receives it.

    Args:
        name: TENNCell input name.
        port: RTL port name (after ``rename``).
        encoding_kind: ``fixed`` or ``logic``.
        width: Port width.
        signed: Whether the port is declared signed.
        frac_bits: Fractional bits (``0`` for logic).
    """

    name: str
    port: str
    encoding_kind: str
    width: int
    signed: bool
    frac_bits: int

    def encode(self, value: float) -> int:
        """Return the port's integer value for a real value (not range-checked)."""
        scale = 2**self.frac_bits if self.encoding_kind == "fixed" else 1
        return int(round(value * scale))

    def decode(self, encoded: int) -> float:
        """Return the real value an encoded port value stands for."""
        if self.encoding_kind == "fixed":
            return encoded / 2**self.frac_bits
        return float(encoded)

    def fits(self, encoded: int) -> bool:
        """Whether an integer is representable on the port."""
        if self.signed:
            return -(2 ** (self.width - 1)) <= encoded < 2 ** (self.width - 1)
        return 0 <= encoded < 2**self.width

    def literal(self, encoded: int) -> str:
        """Return a sized SystemVerilog literal of an encoded value."""
        if self.signed:
            sign = "-" if encoded < 0 else ""
            return f"{sign}{self.width}'sd{abs(encoded)}"
        return f"{self.width}'d{encoded}"

    def hex_word(self, encoded: int) -> str:
        """Two's complement masked to the width, zero-padded hex digits."""
        digits = (self.width + 3) // 4
        return format(encoded & ((1 << self.width) - 1), f"0{digits}x")

    def describe(self) -> str:
        sign = "signed" if self.signed else "unsigned"
        if self.encoding_kind == "fixed":
            return f"{sign} {self.width}-bit fixed point with {self.frac_bits} fractional bits"
        return f"{sign} {self.width}-bit logic"


@dataclass(frozen=True, slots=True)
class SvaStimulus:
    """Encoded stimulus of one simulation run.

    Args:
        ports: Root inputs in declaration order (empty for ``--sva-steps``).
        initial: Encoded initial value of each input (row 0).
        records: Encoded values of each record, in ``ports`` order.
        steps: Number of steps after row 0 (the number of records).
        warnings: Messages about values outside ``environment`` ranges.
        note: A comment line for the generated files (for a replay, which
            witness and which row), or ``""``.
        replay_row: For a witness replay, the row on which a property should
            first fail or a cover first be hit; otherwise ``None``.
    """

    ports: tuple[StimulusPort, ...]
    initial: tuple[int, ...]
    records: tuple[tuple[int, ...], ...]
    steps: int
    warnings: tuple[str, ...] = ()
    note: str = ""
    replay_row: int | None = None

    def hex_text(self, header: str) -> str:
        """Return the ``$readmemh`` file: comments, then one line per record."""
        names = ", ".join(f"{p.name} ({p.port}, {p.width} bits)" for p in self.ports)
        lines = [
            header,
            *([f"// {self.note}"] if self.note else []),
            f"// {len(self.records)} records x {len(self.ports)} inputs: {names}",
        ]
        for record in self.records:
            lines.append(
                " ".join(
                    port.hex_word(value) for port, value in zip(self.ports, record)
                )
            )
        return "\n".join(lines) + "\n"

    def decoded_csv(self) -> str:
        """Return the decoded records for ``nnc-verify --inputs``."""
        lines = [",".join(port.name for port in self.ports)]
        for record in self.records:
            lines.append(
                ",".join(
                    repr(port.decode(value)) for port, value in zip(self.ports, record)
                )
            )
        return "\n".join(lines) + "\n"


def check_stimulus_source(
    system: "NncSystem", source: SvaStimulusSource | None, simulation: bool
) -> None:
    """Check that the stimulus source fits the model and the mode.

    Raises:
        VerificationError: If simulation needs a source that is missing, a
            source is given without simulation, or the source does not fit the
            model (inputs for a model without inputs, steps for one with).
    """
    has_inputs = bool(system.input_variables)
    chosen = (
        []
        if source is None
        else [
            option
            for option, value in (
                ("--sva-inputs", source.inputs),
                ("--sva-steps", source.steps),
                ("--sva-replay", source.witness),
            )
            if value is not None
        ]
    )
    given = bool(chosen)
    if not simulation:
        if given:
            raise VerificationError(
                "--sva-inputs, --sva-steps and --sva-replay are for simulation "
                "(mode simulation or both)"
            )
        return
    if len(chosen) > 1:
        raise VerificationError(f"give only one of {', '.join(chosen)}")
    if not given:
        if has_inputs:
            raise VerificationError(
                "SVA simulation of a model with inputs needs --sva-inputs FILE "
                f"(inputs: {', '.join(system.input_variables)})"
            )
        raise VerificationError(
            "SVA simulation of a model without inputs needs --sva-steps N"
        )
    assert source is not None
    if source.inputs is not None and not has_inputs:
        raise VerificationError(
            "--sva-inputs is for models with inputs; this model has none: use --sva-steps"
        )
    if source.steps is not None and has_inputs:
        raise VerificationError(
            "--sva-steps is for models without inputs; this model has inputs "
            f"({', '.join(system.input_variables)}): use --sva-inputs"
        )
    if source.steps is not None and source.steps < 0:
        raise VerificationError("--sva-steps must be a non-negative integer")


def build_stimulus(
    system: "NncSystem",
    observation: VerilogObservation,
    source: SvaStimulusSource,
    config: "VerificationConfig | None",
) -> SvaStimulus:
    """Encode the stimulus of one run.

    Args:
        system: Root model.
        observation: Observation of its generated RTL module.
        source: Input file or number of steps (checked by
            ``check_stimulus_source``).
        config: Verification config, for ``environment`` ranges.

    Returns:
        The encoded stimulus.

    Raises:
        VerificationError: For an input that is not a root input port of the
            RTL, a value that is not finite, or a value (or initial value) that
            does not fit its port; errors on records name the file and line.
    """
    if source.steps is not None:
        return SvaStimulus(ports=(), initial=(), records=(), steps=source.steps)
    if source.witness is not None:
        return _replay_stimulus(system, observation, source.witness)
    assert source.inputs is not None
    ports = _stimulus_ports(system, observation)
    initial = tuple(
        _encode(port, float(system.variables[port.name].value.value), "initial value")
        for port in ports
    )
    path = source.inputs
    records = []
    outside: dict[str, str] = {}
    environment = config.environment if config is not None else {}
    for line, values in read_input_records(
        system, path, source.delimiter, source.skip_lines
    ):
        encoded = []
        for port in ports:
            value = values[port.name]
            where = f"{path}:{line}: input '{port.name}'"
            if not math.isfinite(value):
                raise VerificationError(f"{where} is not finite ({value})")
            encoded.append(_encode(port, value, f"value {value!r}", where))
            bounds = environment.get(port.name)
            if (
                bounds is not None
                and bounds.range is not None
                and not bounds.range[0] <= value <= bounds.range[1]
                and port.name not in outside
            ):
                outside[port.name] = (
                    f"{where} value {value!r} is outside its environment range "
                    f"[{bounds.range[0]:g}, {bounds.range[1]:g}]"
                )
        records.append(tuple(encoded))
    return SvaStimulus(
        ports=ports,
        initial=initial,
        records=tuple(records),
        steps=len(records),
        warnings=tuple(outside.values()),
    )


def _replay_stimulus(
    system: "NncSystem", observation: VerilogObservation, witness: Path
) -> SvaStimulus:
    """Stimulus that replays a witness up to its failing (or hit) row."""
    ports = _stimulus_ports(system, observation) if system.input_variables else ()
    replay = read_witness(
        witness,
        [WitnessPort(port.port, port.width, port.signed) for port in ports],
        observation.reset,
        observation.reset_active_high,
    )
    note = (
        f"replay of {witness.name}: rows 0..{replay.rows}; expected: a property "
        f"first fails, or a cover is first hit, on row {replay.rows} (the witness "
        "is matched to the model by its ports only)"
    )
    initial = tuple(
        _encode(port, float(system.variables[port.name].value.value), "initial value")
        for port in ports
    )
    return SvaStimulus(
        ports=ports,
        initial=initial,
        records=tuple(
            tuple(record[port.port] for port in ports) for record in replay.records
        ),
        steps=replay.rows,
        note=note,
        replay_row=replay.rows,
    )


def _stimulus_ports(
    system: "NncSystem", observation: VerilogObservation
) -> tuple[StimulusPort, ...]:
    ports = []
    for name in system.input_variables:
        signal = observation.signals[name]
        if signal.kind != INPUT_PORT:
            raise VerificationError(
                f"input '{name}' is not a port of the generated RTL (it comes from "
                "an external module), so SVA simulation cannot drive it"
            )
        ports.append(
            StimulusPort(
                name=name,
                port=signal.expression,
                encoding_kind=signal.encoding_kind,
                width=signal.width,
                signed=signal.signed,
                frac_bits=signal.frac_bits,
            )
        )
    return tuple(ports)


def _encode(port: StimulusPort, value: float, what: str, where: str = "") -> int:
    try:
        encoded = port.encode(value)
    except OverflowError:  # a finite value whose scaled value is infinite
        encoded = None
    if encoded is None or not port.fits(encoded):
        place = where or f"input '{port.name}'"
        raise VerificationError(
            f"{place}: {what} does not fit port '{port.port}' ({port.describe()})"
        )
    return encoded
