"""SVA backend: generation options, property selection and source handling.

The checker and testbench text are produced in later slices; this module
decides *what* the SVA backend emits for a model, with which options, and
validates it against the generated RTL (``VerilogTransformer.observe``).
"""

from __future__ import annotations

import shutil
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from ..inputs.yaml.errors import YamlLocatedError
from ..inputs.yaml.locations import YamlLocationIndex
from ..parser.ast.expression import ReferenceExpression, VariableExpression
from .binding import BoundRawEntry, BoundVerification
from .config import (
    EVENTUALLY_WITHIN,
    PERSISTENCE,
    RESPONSE_AFTER,
    RESPONSE_WITHIN,
    RawEntry,
)
from .generic_properties.binding import BoundProperty
from .references import CONSTANT, ResolvedReference

if TYPE_CHECKING:
    from ..transformers.verilog.generation.observation import (
        ObservedSignal,
        VerilogObservation,
    )

SVA = "sva"

SvaMode = Literal["simulation", "formal", "both"]
SvaStyle = Literal["monitor", "concurrent"]
SIMULATION: SvaMode = "simulation"
FORMAL: SvaMode = "formal"
BOTH: SvaMode = "both"
MONITOR: SvaStyle = "monitor"
CONCURRENT: SvaStyle = "concurrent"
SVA_MODES: tuple[SvaMode, ...] = (SIMULATION, FORMAL, BOTH)
SVA_STYLES: tuple[SvaStyle, ...] = (MONITOR, CONCURRENT)

DEFAULT_DEPTH = 20
DEFAULT_MAX_BOUND = 1024
SOURCES_DIR = "sva_sources"

NOTHING_TO_EMIT = (
    "No SVA verification entries found: add verification.backends.sva.raw "
    "entries or verification.properties that the SVA backend can check"
)


class SvaOptionsError(ValueError):
    """Invalid combination of SVA generation options."""


@dataclass(frozen=True, slots=True)
class SvaOptions:
    """How the SVA backend generates its files (execution choices, not model).

    ``None`` means "not given"; ``effective_*`` properties apply the defaults.

    Args:
        mode: ``simulation``, ``formal`` or ``both``.
        style: ``monitor`` (procedural checker) or ``concurrent``
            (``assert property``).
        depth: Formal depth in property rows (formal or both only).
        sources: External RTL files copied next to the generated files.
        max_bound: Largest ``after``/``within``/``from_step`` accepted.
    """

    mode: SvaMode = SIMULATION
    style: SvaStyle = MONITOR
    depth: int | None = None
    sources: tuple[Path, ...] = ()
    max_bound: int | None = None

    def __post_init__(self) -> None:
        if self.mode not in SVA_MODES:
            raise SvaOptionsError(
                f"SVA mode must be one of: {', '.join(SVA_MODES)}, not {self.mode!r}"
            )
        if self.style not in SVA_STYLES:
            raise SvaOptionsError(
                f"SVA style must be one of: {', '.join(SVA_STYLES)}, not {self.style!r}"
            )
        for label, value in (("depth", self.depth), ("maximum bound", self.max_bound)):
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool)
            ):
                raise SvaOptionsError(f"SVA {label} must be an integer, not {value!r}")
        if self.depth is not None:
            if self.mode == SIMULATION:
                raise SvaOptionsError(
                    "an SVA depth applies to formal checks only (mode formal or both)"
                )
            if self.depth < 1:
                raise SvaOptionsError("SVA depth must be a positive integer")
        if self.style == CONCURRENT and self.mode != SIMULATION:
            raise SvaOptionsError(
                "concurrent style is available for simulation only; formal "
                "checks use the monitor style"
            )
        if self.max_bound is not None and self.max_bound < 1:
            raise SvaOptionsError("SVA maximum bound must be a positive integer")

    @property
    def effective_depth(self) -> int:
        """Formal depth after the default is applied.

        Returns:
            ``depth`` when given, otherwise ``DEFAULT_DEPTH`` (20 rows).
        """
        return DEFAULT_DEPTH if self.depth is None else self.depth

    @property
    def effective_max_bound(self) -> int:
        """Bound limit after the default is applied.

        Returns:
            ``max_bound`` when given, otherwise ``DEFAULT_MAX_BOUND`` (1024).
        """
        return DEFAULT_MAX_BOUND if self.max_bound is None else self.max_bound

    @property
    def simulation(self) -> bool:
        """Whether simulation files are generated.

        Returns:
            ``True`` for mode ``simulation`` or ``both``.
        """
        return self.mode in (SIMULATION, BOTH)

    @property
    def formal(self) -> bool:
        """Whether formal files are generated.

        Returns:
            ``True`` for mode ``formal`` or ``both``.
        """
        return self.mode in (FORMAL, BOTH)


@dataclass(frozen=True, slots=True)
class SelectedProperty:
    """A generic property the SVA backend emits.

    Args:
        bound: The bound property.
        signals: Observed RTL signals its conditions read, keyed by TENNCell
            name, in first-use order (trigger first).
    """

    bound: BoundProperty
    signals: dict[str, ObservedSignal]


@dataclass(frozen=True, slots=True)
class SelectedRawEntry:
    """A raw SVA entry with its placeholders resolved against the RTL.

    Args:
        bound: The bound raw entry.
        signals: Observed RTL signals for its variable and imported-port
            placeholders, keyed by TENNCell name; constants stay in the
            entry's segments.
    """

    bound: BoundRawEntry
    signals: dict[str, ObservedSignal]


@dataclass(frozen=True, slots=True)
class SvaSelection:
    """What the SVA backend emits for one model.

    Args:
        options: The generation options.
        trace_semantics: Effective ``trace_semantics`` of the ``sva`` backend.
        properties: Emitted generic properties, in YAML order.
        raw: Raw SVA entries, in YAML order.
        warnings: Messages about skipped or simulation-only properties.
    """

    options: SvaOptions
    trace_semantics: str
    properties: tuple[SelectedProperty, ...]
    raw: tuple[SelectedRawEntry, ...]
    warnings: tuple[str, ...] = field(default=())


def select_sva(
    bound: BoundVerification,
    observation: VerilogObservation,
    options: SvaOptions,
    validate_expression: Callable[[object], None],
    locations: YamlLocationIndex,
) -> SvaSelection:
    """Decide which generic properties and raw entries the SVA backend emits.

    A generic property is used when it has no ``targets`` or lists ``sva``.
    One the backend cannot check (a condition the RTL cannot express, a value
    that is not a plain RTL signal, or a bound above the limit) is an error
    when it lists ``sva`` and is skipped with a warning otherwise.

    Args:
        bound: Verification config bound to the root system.
        observation: Observation of the module the RTL emits for that system.
        options: Generation options.
        validate_expression: The Verilog emitter's expression check; raises
            ``ValueError`` for what the RTL cannot express.
        locations: Source locations used for errors.

    Returns:
        The emitted properties and raw entries, with warnings.

    Raises:
        YamlLocatedError: For a property that lists ``sva`` but cannot be
            checked, a raw placeholder that is not a plain RTL signal, an
            emitted property ID equal to a raw ID, or concurrent style with
            ``weak`` semantics.
        ValueError: If nothing is emitted.
    """
    trace_semantics = bound.config.effective_trace_semantics(SVA)
    if options.style == CONCURRENT and trace_semantics == "weak":
        path = _semantics_path(bound)
        raise locations.error(
            "concurrent SVA style does not support trace_semantics: weak yet; "
            "use the monitor style",
            *path,
        )

    raw = tuple(
        _select_raw(item, observation, locations) for item in bound.raw.get(SVA, ())
    )
    raw_ids = {item.bound.entry.id for item in raw}

    selected: list[SelectedProperty] = []
    skipped: list[str] = []
    for prop in bound.properties:
        spec = prop.property
        if not spec.targets_backend(SVA):
            continue
        reason, signals = _check_property(
            prop, observation, options, validate_expression
        )
        if reason is not None:
            if spec.targets is not None:
                raise _property_error(
                    locations, prop, f"targets sva, but {reason}", "targets"
                )
            skipped.append(f"{spec.id} ({reason})")
            continue
        if spec.id in raw_ids:
            raise _property_error(
                locations, prop, "ID is also used by an sva raw entry", "id"
            )
        selected.append(SelectedProperty(prop, signals))

    if not selected and not raw:
        raise ValueError(NOTHING_TO_EMIT)
    warnings: list[str] = []
    if skipped:
        warnings.append(
            "generic verification properties skipped for SVA: " + "; ".join(skipped)
        )
    return SvaSelection(
        options=options,
        trace_semantics=trace_semantics,
        properties=tuple(selected),
        raw=raw,
        warnings=tuple(warnings),
    )


def check_sources(sources: tuple[Path, ...]) -> None:
    """Check external RTL sources before anything is written.

    Raises:
        SvaOptionsError: If a source is missing or two sources share a file name.
            Names are compared case-insensitively: they are copied into one
            directory, and ``UART.sv`` and ``uart.sv`` are one file on Windows
            and macOS.
    """
    missing = [str(path) for path in sources if not path.is_file()]
    if missing:
        raise SvaOptionsError(f"SVA source files not found: {', '.join(missing)}")
    names: dict[str, Path] = {}
    for path in sources:
        key = path.name.casefold()
        if key in names:
            raise SvaOptionsError(
                f"SVA sources {names[key]} and {path} have the same file "
                f"name '{path.name}' (compared ignoring case)"
            )
        names[key] = path


def copy_sources(sources: tuple[Path, ...], out_dir: Path) -> tuple[Path, ...]:
    """Copy external RTL sources into ``<out_dir>/sva_sources``.

    Every source is checked before anything is copied. Existing files with the
    same names are overwritten; other files already in the directory (for
    example from an earlier generation) are left in place.

    Args:
        sources: External RTL files, as given by the user.
        out_dir: Output directory of the generated files.

    Returns:
        The copied files, in the order given.

    Raises:
        SvaOptionsError: If a source is missing or two sources share a file name.
    """
    check_sources(sources)
    if not sources:
        return ()  # no empty sva_sources/ directory
    target_dir = out_dir / SOURCES_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for path in sources:
        target = target_dir / path.name
        shutil.copyfile(path, target)
        copied.append(target)
    return tuple(copied)


def _check_property(
    prop: BoundProperty,
    observation: VerilogObservation,
    options: SvaOptions,
    validate_expression: Callable[[object], None],
) -> tuple[str | None, dict[str, ObservedSignal]]:
    """Return why the SVA backend cannot check a property (or ``None``), and
    the RTL signals it reads."""
    if prop.functions:
        names = ", ".join(sorted(prop.functions))
        return (
            f"calls {names}; SVA conditions are RTL expressions without function calls",
            {},
        )
    for condition in (prop.trigger, prop.condition):
        if condition is None:
            continue
        try:
            validate_expression(condition)
        except ValueError as error:
            return f"its condition cannot be expressed in RTL ({error})", {}
    limit = options.effective_max_bound
    for label, value in _bounds(prop):
        if value > limit:
            return f"{label} {value} is above the SVA bound limit {limit}", {}
    signals: dict[str, ObservedSignal] = {}
    for name in _referenced_names(prop):
        signal = observation.signals.get(name)
        if signal is None or not signal.connectable:
            return (
                f"reads '{name}', which is not a plain signal in the generated RTL",
                {},
            )
        signals.setdefault(name, signal)
    return None, signals


def _bounds(prop: BoundProperty) -> Iterator[tuple[str, int]]:
    spec = prop.property
    if spec.after is not None and spec.kind in (RESPONSE_AFTER, PERSISTENCE):
        yield "after", spec.after
    if spec.within is not None and spec.kind in (EVENTUALLY_WITHIN, RESPONSE_WITHIN):
        yield "within upper bound", spec.within[1]
    yield "from_step", spec.from_step


def _referenced_names(prop: BoundProperty) -> Iterator[str]:
    """TENNCell names the conditions read (trigger first), FSM states excluded."""
    for condition in (prop.trigger, prop.condition):
        if condition is None:
            continue
        for node in _walk(condition):
            if isinstance(node, VariableExpression):
                yield node.variable.name
            elif isinstance(node, ReferenceExpression):
                reference = ".".join(node.parts)
                if reference not in prop.states:
                    yield reference


def _walk(node: object) -> Iterator[object]:
    yield node
    for attribute in ("left", "right", "expression"):
        child = getattr(node, attribute, None)
        if child is not None and not isinstance(child, (int, float)):
            yield from _walk(child)
    for argument in getattr(node, "arguments", []):
        yield from _walk(argument)


def _select_raw(
    item: BoundRawEntry,
    observation: VerilogObservation,
    locations: YamlLocationIndex,
) -> SelectedRawEntry:
    signals: dict[str, ObservedSignal] = {}
    for segment in item.segments:
        if not isinstance(segment, ResolvedReference) or segment.kind == CONSTANT:
            continue
        signal = observation.signals.get(segment.target)
        if signal is None or not signal.connectable:
            raise _entry_error(
                locations,
                item.entry,
                f"placeholder '${{{segment.name}}}' names '{segment.target}', which "
                "is not a plain signal in the generated RTL",
            )
        signals.setdefault(segment.target, signal)
    return SelectedRawEntry(item, signals)


def _semantics_path(bound: BoundVerification) -> tuple[object, ...]:
    section = bound.config.backend(SVA)
    if section is not None and section.trace_semantics is not None:
        return ("verification", "backends", SVA, "trace_semantics")
    return ("verification", "trace_semantics")


def _property_error(
    locations: YamlLocationIndex, prop: BoundProperty, message: str, key: str
) -> YamlLocatedError:
    spec = prop.property
    return locations.error(
        f"Verification property '{spec.id}': {message}", *spec.yaml_path, key
    )


def _entry_error(
    locations: YamlLocationIndex, entry: RawEntry, message: str
) -> YamlLocatedError:
    return locations.error(
        f"Raw entry '{entry.id}': {message}", *entry.yaml_path, "code"
    )
