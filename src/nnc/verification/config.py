"""Configuration objects for the TENNCell ``verification`` YAML section."""

from __future__ import annotations

from dataclasses import dataclass, field

ACCEPTED_BACKENDS: tuple[str, ...] = ("native", "mc2", "sva")
RESERVED_BACKENDS: tuple[str, ...] = ("prism", "spin", "english", "custom")
TRACE_SEMANTICS: tuple[str, ...] = ("strict", "weak")

YamlPath = tuple[object, ...]


@dataclass(frozen=True, slots=True)
class InputEnvironment:
    """Assumptions about one root TENNCell input variable.

    Args:
        range: Optional inclusive ``(lo, hi)`` bounds for the input value.
    """

    range: tuple[float, float] | None = None


@dataclass(frozen=True, slots=True)
class RawEntry:
    """One backend-language raw verification entry.

    Args:
        id: Entry identifier, unique within its backend.
        code: Raw backend text with ``${name}`` placeholders. One final newline
            from a YAML block scalar is already stripped.
        description: Optional human-readable description.
        yaml_path: Effective YAML path of the entry, used for located errors.
    """

    id: str
    code: str
    description: str | None
    yaml_path: YamlPath


ALWAYS = "always"
NEVER = "never"
EVENTUALLY = "eventually"
EVENTUALLY_WITHIN = "eventually_within"
RESPONSE_AFTER = "response_after"
RESPONSE_WITHIN = "response_within"
PERSISTENCE = "persistence"
COVER = "cover"
PROPERTY_KINDS: tuple[str, ...] = (
    ALWAYS,
    NEVER,
    EVENTUALLY,
    EVENTUALLY_WITHIN,
    RESPONSE_AFTER,
    RESPONSE_WITHIN,
    PERSISTENCE,
    COVER,
)


@dataclass(frozen=True, slots=True)
class GenericProperty:
    """One backend-neutral verification property (spec section 4).

    Args:
        id: Property identifier, unique among generic properties.
        kind: One of ``PROPERTY_KINDS``.
        condition: Condition text ``P`` (TENNCell guard syntax).
        condition_key: YAML key holding ``P`` (``always``, ``then``, ...).
        trigger: Trigger text ``T`` for ``when`` kinds, else ``None``.
        after: Row offset for ``response_after`` and ``persistence``, else ``None``.
        within: Inclusive ``(a, b)`` row window for ``*_within`` kinds, else ``None``.
        from_step: First row (by position) at which the property is evaluated.
        targets: Explicit target backend names, or ``None`` for the default.
        description: Optional human-readable description.
        yaml_path: Effective YAML path of the property, used for located errors.
    """

    id: str
    kind: str
    condition: str
    condition_key: str
    trigger: str | None
    after: int | None
    within: tuple[int, int] | None
    from_step: int
    targets: tuple[str, ...] | None
    description: str | None
    yaml_path: YamlPath

    def targets_backend(self, backend: str) -> bool:
        """Return whether the property is meant for a backend (no targets: all)."""
        return self.targets is None or backend in self.targets


@dataclass(frozen=True, slots=True)
class BackendSection:
    """Settings and raw entries for one named verification backend.

    Args:
        name: Backend name, one of ``ACCEPTED_BACKENDS``.
        trace_semantics: Optional override of the global trace semantics.
        raw: Raw entries in YAML order.
    """

    name: str
    trace_semantics: str | None = None
    raw: tuple[RawEntry, ...] = ()


@dataclass(frozen=True, slots=True)
class VerificationConfig:
    """Parsed ``verification`` section of one root TENNCell YAML file.

    Args:
        environment: Input assumptions keyed by root input variable name.
        trace_semantics: Global end-of-trace semantics, ``strict`` or ``weak``.
        properties: Generic properties in YAML order.
        backends: Backend sections keyed by backend name.
    """

    environment: dict[str, InputEnvironment] = field(default_factory=dict)
    trace_semantics: str = "strict"
    properties: tuple[GenericProperty, ...] = ()
    backends: dict[str, BackendSection] = field(default_factory=dict)

    def backend(self, name: str) -> BackendSection | None:
        """Return the backend section with this name, if present."""
        return self.backends.get(name)

    def effective_trace_semantics(self, name: str) -> str:
        """Return the trace semantics for a backend after its override."""
        section = self.backends.get(name)
        if section is not None and section.trace_semantics is not None:
            return section.trace_semantics
        return self.trace_semantics
