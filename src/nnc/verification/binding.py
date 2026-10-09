"""Bind a parsed verification config to a TENNCell system."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..inputs.yaml.errors import YamlLocatedError
from ..inputs.yaml.locations import YamlLocationIndex
from .config import RawEntry, VerificationConfig
from .placeholders import Placeholder, TemplateError, TextSegment, parse_template
from .generic_properties.binding import BoundProperty, bind_property
from .references import ResolvedReference, resolve_reference

if TYPE_CHECKING:
    from ..model.system import NncSystem


@dataclass(frozen=True, slots=True)
class BoundRawEntry:
    """Raw entry whose placeholders are resolved against the model.

    Args:
        entry: Parsed raw entry.
        segments: Literal text and resolved references, in source order.
    """

    entry: RawEntry
    segments: tuple[TextSegment | ResolvedReference, ...]


@dataclass(frozen=True, slots=True)
class BoundVerification:
    """Verification config bound to one TENNCell system.

    Args:
        config: Parsed verification config.
        raw: Bound raw entries keyed by backend name.
        properties: Bound generic properties in YAML order.
    """

    config: VerificationConfig
    raw: dict[str, tuple[BoundRawEntry, ...]]
    properties: tuple[BoundProperty, ...] = ()


def bind_verification(
    config: VerificationConfig,
    system: "NncSystem",
    locations: YamlLocationIndex,
) -> BoundVerification:
    """Check model-dependent verification rules and resolve raw placeholders.

    Args:
        config: Parsed verification config.
        system: Root TENNCell system the config belongs to.
        locations: Source locations for the root YAML document.

    Returns:
        The config with every raw entry's placeholders resolved.

    Raises:
        YamlLocatedError: If an environment key is not a root input variable,
            a raw placeholder is malformed, unknown, or ambiguous, or a generic
            property condition does not bind (see ``bind_property``).
    """
    for name in config.environment:
        if name not in system.input_variables:
            raise locations.error(
                f"verification.environment.{name} must name a root input variable",
                "verification",
                "environment",
                name,
            )
    raw = {
        name: tuple(_bind_entry(entry, system, locations) for entry in section.raw)
        for name, section in config.backends.items()
    }
    properties = tuple(
        bind_property(prop, system, locations) for prop in config.properties
    )
    return BoundVerification(config=config, raw=raw, properties=properties)


def _bind_entry(
    entry: RawEntry, system: "NncSystem", locations: YamlLocationIndex
) -> BoundRawEntry:
    try:
        template = parse_template(entry.code)
    except TemplateError as e:
        raise _entry_error(locations, entry, str(e)) from e
    segments: list[TextSegment | ResolvedReference] = []
    for segment in template:
        if isinstance(segment, Placeholder):
            try:
                segments.append(resolve_reference(segment.name, system))
            except ValueError as e:
                raise _entry_error(locations, entry, str(e)) from e
        else:
            segments.append(segment)
    return BoundRawEntry(entry=entry, segments=tuple(segments))


def _entry_error(
    locations: YamlLocationIndex, entry: RawEntry, message: str
) -> YamlLocatedError:
    return locations.error(
        f"Raw entry '{entry.id}': {message}", *entry.yaml_path, "code"
    )
