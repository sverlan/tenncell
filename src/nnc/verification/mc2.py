"""Render bound MC2 raw entries and generic properties into MC2 query files."""

from __future__ import annotations

from dataclasses import dataclass

from ..inputs.yaml.locations import YamlLocationIndex
from .binding import BoundRawEntry, BoundVerification
from .config import EVENTUALLY, RawEntry
from .generic_properties.binding import BoundProperty
from .generic_properties.conditions import decimal_literal as render_literal
from .generic_properties.mc2 import (
    MC2,
    translate_property,
    unsupported_reason,
    weak_approximation,
)
from .placeholders import TextSegment
from .references import CONSTANT, IMPORTED, ResolvedReference

QUERIES_SUFFIX = ".mc2.pltl"
IDS_SUFFIX = ".mc2.ids"
COLUMNS_SUFFIX = ".mc2.columns"


@dataclass(frozen=True, slots=True)
class Mc2Artifacts:
    """Rendered MC2 queries plus their IDs and required trace columns.

    Args:
        queries: One MC2 query per raw entry (YAML order), then one per emitted
            generic property (YAML order).
        ids: Entry and property IDs in the same order as ``queries``.
        columns: Trace columns referenced by the queries, in first-use order
            (raw entries first).
        warnings: Messages about skipped or approximated generic properties.
    """

    queries: tuple[str, ...]
    ids: tuple[str, ...]
    columns: tuple[str, ...]
    warnings: tuple[str, ...] = ()

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


def render_mc2(bound: BoundVerification, locations: YamlLocationIndex) -> Mc2Artifacts:
    """Render the bound ``mc2`` raw entries and the generic properties for MC2.

    A generic property is emitted when it has no ``targets`` or its targets
    include ``mc2``. One that MC2 cannot express (a function call) is an error
    when it targets ``mc2`` explicitly, and is skipped with a warning otherwise.

    Args:
        bound: Verification config bound to the root system.
        locations: Source locations used for entry and property errors.

    Returns:
        Queries, IDs, required trace columns, and warnings.

    Raises:
        YamlLocatedError: If a raw entry is empty or spans several lines, a
            property targeting ``mc2`` explicitly cannot be expressed, or an
            emitted property ID equals a raw entry ID.
    """
    queries: list[str] = []
    ids: list[str] = []
    columns: dict[str, None] = {}
    for item in bound.raw.get(MC2, ()):
        _check_single_query(item.entry, locations)
        queries.append(_render_entry(item, columns, locations))
        ids.append(item.entry.id)
    raw_ids = set(ids)
    semantics = bound.config.effective_trace_semantics(MC2)
    skipped: list[str] = []
    approximated: list[str] = []
    strict_eventually: list[str] = []
    for prop in bound.properties:
        spec = prop.property
        if not spec.targets_backend(MC2):
            continue
        reason = unsupported_reason(prop)
        if reason is not None:
            if spec.targets is not None:
                raise _property_error(
                    locations, prop, f"targets mc2, but {reason}", "targets"
                )
            skipped.append(f"{spec.id} ({reason})")
            continue
        if spec.id in raw_ids:
            raise _property_error(
                locations, prop, "ID is also used by an mc2 raw entry", "id"
            )
        queries.append(translate_property(prop, semantics))
        ids.append(spec.id)
        for column in prop.columns:
            columns.setdefault(column, None)
        if semantics == "weak" and weak_approximation(prop):
            approximated.append(spec.id)
        elif semantics == "weak" and spec.kind == EVENTUALLY:
            strict_eventually.append(spec.id)
    warnings = []
    if skipped:
        warnings.append(
            "generic verification properties skipped for MC2: " + "; ".join(skipped)
        )
    if approximated:
        warnings.append(
            "trace_semantics weak: MC2 counts obligations still open at the end of "
            f"the trace as satisfied (native reports pending): {', '.join(approximated)}"
        )
    if strict_eventually:
        warnings.append(
            "trace_semantics weak: MC2 checks unbounded 'eventually' strictly, so an "
            "unmet condition gives 0 (native reports pending): "
            f"{', '.join(strict_eventually)}"
        )
    return Mc2Artifacts(tuple(queries), tuple(ids), tuple(columns), tuple(warnings))


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


def _property_error(
    locations: YamlLocationIndex, prop: BoundProperty, message: str, key: str
):
    spec = prop.property
    return locations.error(
        f"Verification property '{spec.id}': {message}", *spec.yaml_path, key
    )


def _entry_error(locations: YamlLocationIndex, entry: RawEntry, message: str):
    return locations.error(
        f"Raw entry '{entry.id}': {message}", *entry.yaml_path, "code"
    )


def _lines(items: tuple[str, ...]) -> str:
    return "".join(f"{item}\n" for item in items)
