"""Render bound MC2 raw verification entries into MC2 query files."""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal

from ..inputs.yaml.locations import YamlLocationIndex
from .binding import BoundRawEntry, BoundVerification
from .config import RawEntry
from .placeholders import TextSegment
from .references import CONSTANT, IMPORTED, ResolvedReference

QUERIES_SUFFIX = ".mc2.pltl"
IDS_SUFFIX = ".mc2.ids"
COLUMNS_SUFFIX = ".mc2.columns"


@dataclass(frozen=True, slots=True)
class Mc2Artifacts:
    """Rendered MC2 queries plus their IDs and required trace columns.

    Args:
        queries: One MC2 query per raw entry, in YAML order.
        ids: Raw entry IDs in the same order as ``queries``.
        columns: Trace columns referenced by the queries, in first-use order.
    """

    queries: tuple[str, ...]
    ids: tuple[str, ...]
    columns: tuple[str, ...]

    def files(self) -> dict[str, str]:
        """Return output file contents keyed by file suffix."""
        return {
            QUERIES_SUFFIX: _lines(self.queries),
            IDS_SUFFIX: _lines(self.ids),
            COLUMNS_SUFFIX: _lines(self.columns),
        }


def column_name(reference: ResolvedReference) -> str:
    """Return the MC2 trace column name for a variable or imported reference."""
    if reference.kind == IMPORTED:
        return reference.target.replace(".", "__")
    return reference.target


def render_literal(value: float) -> str:
    """Render a constant as a plain MC2 number without exponent notation."""
    if not math.isfinite(value):
        raise ValueError(f"Cannot render non-finite constant {value} for MC2")
    if value.is_integer():
        return str(int(value))
    return format(Decimal(repr(value)), "f")


def render_mc2(
    bound: BoundVerification, locations: YamlLocationIndex
) -> Mc2Artifacts:
    """Render the bound ``mc2`` raw entries.

    Args:
        bound: Verification config bound to the root system.
        locations: Source locations used for entry errors.

    Returns:
        Queries, IDs, and required trace columns.

    Raises:
        YamlLocatedError: If an entry is empty or spans several lines.
    """
    queries: list[str] = []
    ids: list[str] = []
    columns: dict[str, None] = {}
    for item in bound.raw.get("mc2", ()):
        _check_single_query(item.entry, locations)
        queries.append(_render_entry(item, columns, locations))
        ids.append(item.entry.id)
    return Mc2Artifacts(tuple(queries), tuple(ids), tuple(columns))


def _check_single_query(entry: RawEntry, locations: YamlLocationIndex) -> None:
    if not entry.code.strip():
        raise _entry_error(locations, entry, "MC2 query must not be empty")
    if "\n" in entry.code or "\r" in entry.code:
        raise _entry_error(
            locations,
            entry,
            "MC2 query must be a single line; use YAML folded style `>-` "
            "for long queries",
        )


def _render_entry(
    item: BoundRawEntry, columns: dict[str, None], locations: YamlLocationIndex
) -> str:
    parts: list[str] = []
    for segment in item.segments:
        if isinstance(segment, TextSegment):
            parts.append(segment.text)
        elif segment.kind == CONSTANT:
            assert segment.value is not None
            try:
                parts.append(render_literal(segment.value))
            except ValueError as e:
                raise _entry_error(locations, item.entry, str(e)) from e
        else:
            column = column_name(segment)
            columns.setdefault(column, None)
            parts.append(column)
    return "".join(parts)


def _entry_error(locations: YamlLocationIndex, entry: RawEntry, message: str):
    return locations.error(
        f"Raw entry '{entry.id}': {message}", *entry.yaml_path, "code"
    )


def _lines(items: tuple[str, ...]) -> str:
    return "".join(f"{item}\n" for item in items)
