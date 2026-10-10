"""Read delimited trace and input files (``nnc-verify``, SVA stimulus)."""

from __future__ import annotations

import csv
import math
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

from .generic_properties.native import VerificationError

if TYPE_CHECKING:
    from ..model.system import NncSystem


def iter_records(
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


def check_header(path: Path, line: int, header: list[str]) -> None:
    """Reject empty column names in a header."""
    for index, name in enumerate(header, start=1):
        if not name:
            raise VerificationError(f"{path}:{line}: column {index} has an empty name")


def parse_number(
    path: Path, line: int, column: str, text: str, label: bool = False
) -> int | float:
    """Parse one field as a number; integral labels become ``int``."""
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


def read_input_records(
    system: "NncSystem", path: Path, delimiter: str, skip_lines: int = 0
) -> list[tuple[int, dict[str, float]]]:
    """Read an input file: a header naming each root input once, then records.

    A header without records is valid (zero records).

    Args:
        system: Model whose root inputs the file gives.
        path: Input file.
        delimiter: Field delimiter; ``" "`` means any run of whitespace.
        skip_lines: Number of lines to skip before the header.

    Returns:
        ``(line number, values)`` for every record, values keyed by input name.

    Raises:
        VerificationError: For an empty file, an empty, duplicate, unknown or
            missing column, a record with a different number of fields, or a
            value that is not a number.
    """
    records = list(iter_records(path, delimiter, skip_lines))
    if not records:
        raise VerificationError(f"{path}: input file is empty")
    header_line, header = records[0]
    check_header(path, header_line, header)
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
    result = []
    for line, fields in records[1:]:
        if len(fields) != len(header):
            raise VerificationError(
                f"{path}:{line}: expected {len(header)} fields, found {len(fields)}"
            )
        result.append(
            (
                line,
                {
                    name: float(parse_number(path, line, name, text))
                    for name, text in zip(header, fields)
                },
            )
        )
    return result
