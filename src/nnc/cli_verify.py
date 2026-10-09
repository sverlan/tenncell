"""CLI tool ``nnc-verify``: check generic verification properties with ``native``."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from collections.abc import Iterable
from pathlib import Path

from nnc._version import __version__
from nnc.cli_transform import _parse_verification_configs
from nnc.model.system import NncSystem
from nnc.verification.binding import BoundVerification
from nnc.verification.generic_properties.native import (
    FAIL,
    NATIVE,
    PropertyResult,
    Trace,
    VerificationError,
    check_properties,
)

STEP_COLUMNS = ("step", "_step", "time", "Time")
_OPEN_SHOWN = 10


def main() -> int:
    """Run ``nnc-verify`` and return its exit code.

    Returns:
        ``0`` when no property fails, ``1`` when a property fails or an
        operational error occurs. Usage errors exit with ``2`` (argparse).
    """
    args = _parser().parse_args()
    try:
        return _run(args)
    except (VerificationError, ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nnc-verify",
        description=(
            f"TENNCell verifier v{__version__} - check generic verification "
            "properties with the built-in native checker"
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"nnc-verify {__version__}"
    )
    parser.add_argument("system_file", type=Path, help="TENNCell system file (.yaml)")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--trace", type=Path, help="Check a recorded trace file")
    source.add_argument(
        "--inputs", type=Path, help="Simulate on an input CSV, then check the trace"
    )
    source.add_argument(
        "--steps", type=int, help="Simulate an autonomous model for N steps, then check"
    )
    parser.add_argument(
        "--delimiter",
        type=_delimiter,
        default=",",
        help='Field delimiter of --trace and --inputs files; " " means any whitespace '
        "(default: comma)",
    )
    parser.add_argument(
        "--first-step",
        type=int,
        default=0,
        help="Label of the first row of a trace without a step column (default: 0)",
    )
    parser.add_argument(
        "--no-step-column",
        action="store_true",
        help="Label --trace rows by position even if the first column is named "
        "step, _step, time or Time; that column is then ordinary data",
    )
    parser.add_argument(
        "--skip-lines",
        type=_non_negative,
        default=0,
        help="Skip N lines (such as a preamble) before the header of --trace and "
        "--inputs files (default: 0)",
    )
    parser.add_argument("--json", action="store_true", help="Print results as JSON")
    parser.add_argument(
        "--import-path",
        action="append",
        default=[],
        help="Additional directory to search for imported TENNCell files",
    )
    parser.add_argument(
        "--import-paths", default="", help="Path-separated list of import directories"
    )
    return parser


def _delimiter(text: str) -> str:
    """Accept a single-character delimiter, or a space meaning any whitespace."""
    if len(text) != 1:
        raise argparse.ArgumentTypeError(
            f"must be a single character or ' ' (any whitespace), not {text!r}"
        )
    return text


def _non_negative(text: str) -> int:
    """Accept a non-negative integer."""
    try:
        value = int(text)
    except ValueError:
        value = -1
    if value < 0:
        raise argparse.ArgumentTypeError(
            f"must be a non-negative integer, not {text!r}"
        )
    return value


def _run(args: argparse.Namespace) -> int:
    if args.steps is not None and args.steps < 0:
        raise VerificationError("--steps must be a non-negative integer")
    import_paths = list(args.import_path) + [
        path for path in args.import_paths.split(os.pathsep) if path
    ]
    raw_cache: dict[Path, dict] = {}
    system = NncSystem.from_yaml(
        str(args.system_file), import_paths=import_paths, _raw_data_cache=raw_cache
    )
    bound = _parse_verification_configs([system], raw_cache)[system.source_path]  # type: ignore[index]
    if bound is None or not bound.properties:
        raise VerificationError(
            "No generic verification properties found (verification.properties)"
        )
    if args.trace is not None:
        trace = read_trace(
            args.trace,
            _required_columns(bound),
            args.delimiter,
            args.first_step,
            step_column=not args.no_step_column,
            skip_lines=args.skip_lines,
        )
    elif args.inputs is not None:
        trace = simulate_inputs(system, args.inputs, args.delimiter, args.skip_lines)
    else:
        trace = simulate_steps(system, args.steps)
    results = check_properties(bound, system, trace)
    print(_format_json(results) if args.json else _format_table(results))
    return 1 if any(result.status == FAIL for result in results) else 0


def _required_columns(bound: BoundVerification) -> set[str]:
    return {
        column
        for prop in bound.properties
        if prop.property.targets_backend(NATIVE)
        for column in prop.columns
    }


# Recorded traces -------------------------------------------------------------


def read_trace(
    path: Path,
    required: set[str],
    delimiter: str,
    first_step: int = 0,
    step_column: bool = True,
    skip_lines: int = 0,
) -> Trace:
    """Read a recorded trace file.

    A first column named ``step``, ``_step``, ``time`` or ``Time`` gives the row
    labels (unless ``step_column`` is false); otherwise rows are labelled
    ``first_step``, ``first_step + 1``, ... Only the ``required`` columns are read
    as numbers; other columns, including columns with an empty name (such as
    PeP's separator column), are ignored.

    Args:
        path: Trace file with a header line.
        required: Columns used by the properties being checked.
        delimiter: Field delimiter; ``" "`` means any run of whitespace.
        first_step: Label of the first row when rows are labelled by position.
        step_column: Whether a step-named first column gives the labels.
        skip_lines: Number of lines to skip before the header.

    Returns:
        The trace (columns absent from the file are left for the checker to report).

    Raises:
        VerificationError: For an empty file, duplicate column names, rows with a
            different number of fields, non-numeric labels or required values, or
            labels that are not finite and strictly increasing.
    """
    records = list(_records(path, delimiter, skip_lines))
    if not records:
        raise VerificationError(f"{path}: trace file is empty")
    header_line, header = records[0]
    named = [name for name in header if name]
    duplicates = sorted({name for name in named if named.count(name) > 1})
    if duplicates:
        raise VerificationError(
            f"{path}:{header_line}: duplicate column names: {', '.join(duplicates)}"
        )
    has_step = step_column and header[0] in STEP_COLUMNS
    # The label column can also be data, e.g. a model variable named `time`.
    used = {name: index for index, name in enumerate(header) if name in required}
    labels: list[int | float] = []
    rows: list[dict[str, float]] = []
    for position, (line, fields) in enumerate(records[1:]):
        if len(fields) != len(header):
            raise VerificationError(
                f"{path}:{line}: expected {len(header)} fields, found {len(fields)}"
            )
        if has_step:
            labels.append(_number(path, line, header[0], fields[0], label=True))
        else:
            labels.append(first_step + position)
        rows.append(
            {
                name: _number(path, line, name, fields[index])
                for name, index in used.items()
            }
        )
    if not rows:
        raise VerificationError(f"{path}: trace has a header but no data rows")
    try:
        trace = Trace(labels, rows)
    except VerificationError as error:
        hint = (
            f"; if column '{header[0]}' is not a step counter, use --no-step-column"
            if has_step and "label" in str(error)
            else ""
        )
        raise VerificationError(f"{path}: {error}{hint}") from error
    _warn_about_gaps(path, labels)
    return trace


def _records(
    path: Path, delimiter: str, skip_lines: int = 0
) -> Iterable[tuple[int, list[str]]]:
    """Yield ``(line number, fields)`` for every non-blank line after the first
    ``skip_lines`` lines; line numbers count every line of the file."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        for _ in range(skip_lines):
            if not handle.readline():
                return
        if delimiter == " ":
            for line_number, line in enumerate(handle, start=skip_lines + 1):
                if line.strip():
                    yield line_number, line.split()
            return
        reader = csv.reader(handle, delimiter=delimiter)
        try:
            for fields in reader:
                if not fields or (len(fields) == 1 and not fields[0].strip()):
                    continue  # a blank or whitespace-only line
                yield skip_lines + reader.line_num, [field.strip() for field in fields]
        except csv.Error as error:
            line_number = skip_lines + reader.line_num
            raise VerificationError(f"{path}:{line_number}: {error}") from error


def _check_header(path: Path, line: int, header: list[str]) -> None:
    """Reject empty column names in a header."""
    for index, name in enumerate(header, start=1):
        if not name:
            raise VerificationError(f"{path}:{line}: column {index} has an empty name")


def _number(
    path: Path, line: int, column: str, text: str, label: bool = False
) -> int | float:
    try:
        value = float(text)
    except ValueError:
        kind = "step label" if label else f"value in column '{column}'"
        raise VerificationError(
            f"{path}:{line}: {kind} is not a number: {text!r}"
        ) from None
    if label and math.isfinite(value) and value.is_integer():
        return int(value)  # integral labels are reported as integers
    return value


def _warn_about_gaps(path: Path, labels: list[int | float]) -> None:
    if not all(math.isfinite(label) and float(label).is_integer() for label in labels):
        return
    for previous, label in zip(labels, labels[1:]):
        if label - previous != 1:
            print(
                f"Warning: {path}: step labels jump from {previous} to {label}; "
                "after/within count rows, not steps",
                file=sys.stderr,
            )
            return


# Simulation ------------------------------------------------------------------


def simulate_steps(system: NncSystem, steps: int) -> Trace:
    """Simulate an autonomous model: row 0 is the initial state, then N steps.

    Raises:
        VerificationError: If the model has inputs.
    """
    if system.input_variables:
        raise VerificationError(
            "--steps is for models without inputs; this model has inputs "
            f"({', '.join(system.input_variables)}): use --inputs"
        )
    rows = [_snapshot(system)]
    for _ in range(steps):
        system.step()
        rows.append(_snapshot(system))
    return Trace(list(range(len(rows))), rows)


def simulate_inputs(
    system: NncSystem, path: Path, delimiter: str, skip_lines: int = 0
) -> Trace:
    """Simulate a model on input records: row 0 is the initial state, and input
    record k drives the transition to row k.

    Raises:
        VerificationError: If the model has no inputs, or a record has unknown,
            missing, or non-numeric input values.
    """
    if not system.input_variables:
        raise VerificationError(
            "--inputs is for models with inputs; this model has none: use --steps"
        )
    records = list(_records(path, delimiter, skip_lines))
    if not records:
        raise VerificationError(f"{path}: input file is empty")
    header_line, header = records[0]
    _check_header(path, header_line, header)
    duplicates = sorted({name for name in header if header.count(name) > 1})
    if duplicates:
        raise VerificationError(
            f"{path}:{header_line}: duplicate input columns: {', '.join(duplicates)}"
        )
    unknown = [name for name in header if name not in system.input_variables]
    if unknown:
        raise VerificationError(f"{path}: unknown input columns: {', '.join(unknown)}")
    missing = [name for name in system.input_variables if name not in header]
    if missing:
        raise VerificationError(f"{path}: missing input columns: {', '.join(missing)}")
    rows = [_snapshot(system)]
    for line, fields in records[1:]:
        if len(fields) != len(header):
            raise VerificationError(
                f"{path}:{line}: expected {len(header)} fields, found {len(fields)}"
            )
        system.step(
            {
                name: _number(path, line, name, text)
                for name, text in zip(header, fields)
            }
        )
        rows.append(_snapshot(system))
    return Trace(list(range(len(rows))), rows)


def _snapshot(system: NncSystem) -> dict[str, float]:
    """Return all local variables plus imported inputs/outputs as ``alias__port``."""
    row = {
        name: float(variable.value.value) for name, variable in system.variables.items()
    }
    for item in system.imports:
        if item.system is None:
            continue
        ports = {**item.system.input_variables, **item.system.output_variables}
        for port, variable in ports.items():
            row[f"{item.alias}__{port}"] = float(variable.value.value)
    return row


# Output ----------------------------------------------------------------------


def _position(row: int | None, label: int | float | None) -> str:
    return "" if row is None else f"row {row} ({label})"


def _format_table(results: list[PropertyResult]) -> str:
    header = ("id", "kind", "result", "trigger", "reported", "open")
    lines = [
        (
            result.id,
            result.kind,
            result.status,
            _position(result.trigger_row, result.trigger_label),
            _position(result.reported_row, result.reported_label),
            _open(result),
        )
        for result in results
    ]
    widths = [max(len(row[i]) for row in [header, *lines]) for i in range(len(header))]
    return "\n".join(
        "  ".join(cell.ljust(width) for cell, width in zip(row, widths)).rstrip()
        for row in [header, *lines]
    )


def _open(result: PropertyResult) -> str:
    obligations = result.open_obligations
    if not obligations:
        return ""
    shown = [
        "end of trace"
        if o.trigger_row is None
        else _position(o.trigger_row, o.trigger_label)
        for o in obligations[:_OPEN_SHOWN]
    ]
    more = len(obligations) - _OPEN_SHOWN
    return ", ".join(shown) + (f" (+{more} more)" if more > 0 else "")


def _format_json(results: list[PropertyResult]) -> str:
    return json.dumps(
        [
            {
                "id": r.id,
                "kind": r.kind,
                "status": r.status,
                "trigger_row": r.trigger_row,
                "trigger_label": r.trigger_label,
                "reported_row": r.reported_row,
                "reported_label": r.reported_label,
                "open_obligations": [
                    {"trigger_row": o.trigger_row, "trigger_label": o.trigger_label}
                    for o in r.open_obligations
                ],
            }
            for r in results
        ],
        indent=2,
    )


if __name__ == "__main__":
    sys.exit(main())
