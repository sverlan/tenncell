"""Structural parser for the TENNCell ``verification`` YAML section."""

from __future__ import annotations

import re
from typing import Any

from ..inputs.yaml.sections import YamlSectionContext
from .config import (
    ACCEPTED_BACKENDS,
    RESERVED_BACKENDS,
    SVA_MODES,
    TRACE_SEMANTICS,
    ALWAYS,
    COVER,
    EVENTUALLY,
    EVENTUALLY_WITHIN,
    NEVER,
    PERSISTENCE,
    RESPONSE_AFTER,
    RESPONSE_WITHIN,
    BackendSection,
    GenericProperty,
    InputEnvironment,
    RawEntry,
    VerificationConfig,
    YamlPath,
)

_SECTION = "verification"
_TOP_LEVEL_KEYS = ("environment", "trace_semantics", "properties", "backends")
_BACKEND_KEYS = {
    "native": ("trace_semantics",),
    "mc2": ("trace_semantics", "raw"),
    "sva": ("trace_semantics", "mode"),
}
_RAW_ENTRY_KEYS = ("id", "description", "code")
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# Keys that select a property kind; `targets`, `from_step`, ... are shared fields.
_KIND_KEYS = frozenset(
    {
        "always",
        "never",
        "eventually",
        "within",
        "when",
        "then",
        "then_always",
        "after",
        "cover",
    }
)
_PROPERTY_KEYS = (
    "id",
    "description",
    "targets",
    "from_step",
    "always",
    "never",
    "eventually",
    "within",
    "when",
    "then",
    "then_always",
    "after",
    "cover",
)
# Every valid combination of kind keys (spec section 4.2).
_KIND_BY_KEYS: dict[frozenset[str], str] = {
    frozenset({"always"}): ALWAYS,
    frozenset({"never"}): NEVER,
    frozenset({"eventually"}): EVENTUALLY,
    frozenset({"eventually", "within"}): EVENTUALLY_WITHIN,
    frozenset({"when", "then", "after"}): RESPONSE_AFTER,
    frozenset({"when", "then", "within"}): RESPONSE_WITHIN,
    frozenset({"when", "then_always"}): PERSISTENCE,
    frozenset({"when", "then_always", "after"}): PERSISTENCE,
    frozenset({"cover"}): COVER,
}
# YAML key holding the condition `P` of each kind.
_CONDITION_KEY = {
    ALWAYS: "always",
    NEVER: "never",
    EVENTUALLY: "eventually",
    EVENTUALLY_WITHIN: "eventually",
    RESPONSE_AFTER: "then",
    RESPONSE_WITHIN: "then",
    PERSISTENCE: "then_always",
    COVER: "cover",
}
_VALID_COMBINATIONS = (
    "always; never; eventually [+ within]; when + then + (after | within); "
    "when + then_always [+ after]; cover"
)


def _kind_error(keys: frozenset[str]) -> str:
    """Explain why a set of kind keys is not a valid property kind."""
    if not keys:
        return f"defines no property kind; valid kinds: {_VALID_COMBINATIONS}"
    if "then" in keys and "then_always" in keys:
        return "'then' and 'then_always' cannot be combined"
    if "when" in keys and not keys & {"then", "then_always"}:
        return "'when' needs 'then' or 'then_always'"
    if keys & {"then", "then_always"} and "when" not in keys:
        return "'then'/'then_always' needs 'when'"
    if keys >= {"when", "then"} and not keys & {"after", "within"}:
        return "'when' + 'then' needs exactly one of 'after' or 'within'"
    if keys >= {"after", "within"}:
        return "'after' and 'within' cannot be combined"
    return (
        f"invalid combination of keys {', '.join(sorted(keys))}; "
        f"valid kinds: {_VALID_COMBINATIONS}"
    )


def parse_verification_section(
    section: dict | None, context: YamlSectionContext
) -> VerificationConfig | None:
    """Parse the ``verification`` YAML section into a verification config.

    Only structure is validated here. Checks that need the TENNCell model, such
    as placeholder resolution, happen when the config is bound to a system.

    Args:
        section: Raw ``verification`` mapping, or ``None`` when absent.
        context: Section parsing context with source locations.

    Returns:
        The parsed config, or ``None`` when the section is absent.

    Raises:
        YamlLocatedError: If the section violates the verification schema.
    """
    if section is None:
        return None
    parser = _Parser(context)
    return parser.parse(section)


class _Parser:
    """Validate one verification section and report located errors."""

    def __init__(self, context: YamlSectionContext):
        self.context = context

    def error(self, message: str, *path: object):
        """Build a located error for a path under the verification section."""
        return self.context.locations.error(message, _SECTION, *path)

    def parse(self, section: object) -> VerificationConfig:
        """Parse the whole verification section."""
        data = self._mapping(section, "verification must be a mapping")
        self._reject_unknown_keys(data, _TOP_LEVEL_KEYS, "verification")
        trace_semantics = self._trace_semantics(
            data.get("trace_semantics", "strict"), "trace_semantics"
        )
        return VerificationConfig(
            environment=self._environment(data.get("environment")),
            trace_semantics=trace_semantics,
            properties=self._properties(data.get("properties")),
            backends=self._backends(data.get("backends")),
        )

    def _mapping(self, value: object, message: str, *path: object) -> dict:
        if not isinstance(value, dict):
            raise self.error(message, *path)
        return value

    def _reject_unknown_keys(
        self, data: dict, allowed: tuple[str, ...], label: str, *path: object
    ) -> None:
        for key in data:
            if key not in allowed:
                raise self.error(
                    f"Unknown key '{key}' in {label}; allowed keys: "
                    f"{', '.join(allowed)}",
                    *path,
                    key,
                )

    def _trace_semantics(self, value: object, *path: object) -> str:
        if value not in TRACE_SEMANTICS:
            raise self.error(
                f"verification.{'.'.join(str(item) for item in path)} must be "
                f"one of: {', '.join(TRACE_SEMANTICS)}",
                *path,
            )
        return str(value)

    def _identifier(self, value: object, label: str, *path: object) -> str:
        if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
            raise self.error(
                f"{label} must be an identifier ([A-Za-z_][A-Za-z0-9_]*)", *path
            )
        return value

    def _environment(self, raw: object) -> dict[str, InputEnvironment]:
        if raw is None:
            return {}
        data = self._mapping(
            raw, "verification.environment must be a mapping", "environment"
        )
        environment: dict[str, InputEnvironment] = {}
        for name, item in data.items():
            path = ("environment", name)
            if not isinstance(name, str):
                raise self.error(
                    f"verification.environment key '{name}' must be an input variable name",
                    *path,
                )
            if item is None:
                item = {}
            entry = self._mapping(
                item, f"verification.environment.{name} must be a mapping", *path
            )
            if "distribution" in entry:
                raise self.error(
                    f"verification.environment.{name}.distribution is reserved "
                    "and not supported yet",
                    *path,
                    "distribution",
                )
            self._reject_unknown_keys(
                entry, ("range",), f"verification.environment.{name}", *path
            )
            environment[name] = InputEnvironment(
                range=self._range(entry.get("range"), name, *path, "range")
            )
        return environment

    def _range(
        self, raw: object, name: object, *path: object
    ) -> tuple[float, float] | None:
        if raw is None:
            return None
        message = (
            f"verification.environment.{name}.range must be [lo, hi] with lo <= hi"
        )
        if not isinstance(raw, list) or len(raw) != 2:
            raise self.error(message, *path)
        if not all(_is_number(value) for value in raw):
            raise self.error(message, *path)
        lo, hi = float(raw[0]), float(raw[1])
        if lo > hi:
            raise self.error(message, *path)
        return lo, hi

    def _properties(self, raw: object) -> tuple[GenericProperty, ...]:
        if raw is None:
            return ()
        if not isinstance(raw, list):
            raise self.error("verification.properties must be a list", "properties")
        properties: list[GenericProperty] = []
        seen: set[str] = set()
        for index, item in enumerate(raw):
            path: YamlPath = ("properties", index)
            entry = self._mapping(
                item, "Each verification property must be a mapping", *path
            )
            if "id" not in entry:
                raise self.error("Verification property must define 'id'", *path)
            property_id = self._identifier(
                entry["id"], "Verification property id", *path, "id"
            )
            if property_id in seen:
                raise self.error(
                    f"Duplicate verification property id '{property_id}'", *path, "id"
                )
            seen.add(property_id)
            properties.append(self._property(property_id, entry, path))
        return tuple(properties)

    def _property(
        self, property_id: str, entry: dict, path: YamlPath
    ) -> GenericProperty:
        label = f"Verification property '{property_id}'"
        if "probability" in entry:
            raise self.error(
                f"{label}: 'probability' is reserved and not supported yet",
                *path,
                "probability",
            )
        self._reject_unknown_keys(
            entry, _PROPERTY_KEYS, f"verification property '{property_id}'", *path
        )
        kind_keys = frozenset(entry) & _KIND_KEYS
        kind = _KIND_BY_KEYS.get(kind_keys)
        if kind is None:
            raise self.error(f"{label}: {_kind_error(kind_keys)}", *path)
        condition_key = _CONDITION_KEY[kind]
        description = entry.get("description")
        if description is not None and not isinstance(description, str):
            raise self.error(
                f"{label}: description must be a string", *path, "description"
            )
        return GenericProperty(
            id=property_id,
            kind=kind,
            condition=self._condition(
                entry[condition_key], label, *path, condition_key
            ),
            condition_key=condition_key,
            trigger=(
                self._condition(entry["when"], label, *path, "when")
                if "when" in entry
                else None
            ),
            after=self._after(entry, kind, label, *path),
            within=(
                self._window(entry["within"], label, *path, "within")
                if "within" in entry
                else None
            ),
            from_step=self._non_negative(
                entry.get("from_step", 0), f"{label}: from_step", *path, "from_step"
            ),
            targets=self._targets(entry.get("targets"), *path, "targets"),
            description=description,
            yaml_path=(_SECTION, *path),
        )

    def _condition(self, raw: object, label: str, *path: object) -> str:
        if isinstance(raw, bool):
            return "true" if raw else "false"
        if isinstance(raw, str) and raw.strip():
            return raw
        if isinstance(raw, (dict, list)):
            raise self.error(
                f"{label}: conditions must be TENNCell expressions; nested "
                "properties are not supported in v1",
                *path,
            )
        raise self.error(f"{label}: condition must be a non-empty string", *path)

    def _non_negative(self, raw: object, label: str, *path: object) -> int:
        if not isinstance(raw, int) or isinstance(raw, bool) or raw < 0:
            raise self.error(f"{label} must be a non-negative integer", *path)
        return raw

    def _after(self, entry: dict, kind: str, label: str, *path: object) -> int | None:
        if "after" in entry:
            return self._non_negative(entry["after"], f"{label}: after", *path, "after")
        return 0 if kind == PERSISTENCE else None

    def _window(self, raw: object, label: str, *path: object) -> tuple[int, int]:
        message = f"{label}: within must be [a, b] with integers 0 <= a <= b"
        if not isinstance(raw, list) or len(raw) != 2:
            raise self.error(message, *path)
        if not all(isinstance(v, int) and not isinstance(v, bool) for v in raw):
            raise self.error(message, *path)
        start, end = raw
        if start < 0 or start > end:
            raise self.error(message, *path)
        return start, end

    def _targets(self, raw: object, *path: object) -> tuple[str, ...] | None:
        if raw is None:
            return None
        if not isinstance(raw, list) or not all(isinstance(t, str) for t in raw):
            raise self.error("Property targets must be a list of backend names", *path)
        for target in raw:
            self._check_backend_name(target, *path)
        return tuple(raw)

    def _check_backend_name(self, name: object, *path: object) -> None:
        if name in ACCEPTED_BACKENDS:
            return
        if name in RESERVED_BACKENDS:
            raise self.error(
                f"Verification backend '{name}' is reserved and not implemented yet",
                *path,
            )
        raise self.error(
            f"Unknown verification backend '{name}'; accepted backends: "
            f"{', '.join(ACCEPTED_BACKENDS)}",
            *path,
        )

    def _backends(self, raw: object) -> dict[str, BackendSection]:
        if raw is None:
            return {}
        data = self._mapping(raw, "verification.backends must be a mapping", "backends")
        backends: dict[str, BackendSection] = {}
        for name, item in data.items():
            path = ("backends", name)
            self._check_backend_name(name, *path)
            backends[name] = self._backend(name, item, *path)
        return backends

    def _backend(self, name: str, raw: object, *path: object) -> BackendSection:
        if raw is None:
            raw = {}
        data = self._mapping(
            raw, f"verification.backends.{name} must be a mapping", *path
        )
        if "raw" in data and name != "mc2":
            raise self.error(_unsupported_raw_message(name), *path, "raw")
        self._reject_unknown_keys(
            data, _BACKEND_KEYS[name], f"verification.backends.{name}", *path
        )
        trace_semantics = None
        if "trace_semantics" in data:
            trace_semantics = self._trace_semantics(
                data["trace_semantics"], *path, "trace_semantics"
            )
        mode = None
        if name == "sva":
            mode = data.get("mode", "simulation")
            if mode not in SVA_MODES:
                raise self.error(
                    f"verification.backends.sva.mode must be one of: "
                    f"{', '.join(SVA_MODES)}",
                    *path,
                    "mode",
                )
        return BackendSection(
            name=name,
            trace_semantics=trace_semantics,
            mode=mode,
            raw=self._raw_entries(name, data.get("raw"), *path, "raw"),
        )

    def _raw_entries(
        self, backend: str, raw: object, *path: object
    ) -> tuple[RawEntry, ...]:
        if raw is None:
            return ()
        if not isinstance(raw, list):
            raise self.error(
                f"verification.backends.{backend}.raw must be a list", *path
            )
        entries: list[RawEntry] = []
        seen: set[str] = set()
        for index, item in enumerate(raw):
            entry_path = (*path, index)
            data = self._mapping(item, "Each raw entry must be a mapping", *entry_path)
            self._reject_unknown_keys(
                data, _RAW_ENTRY_KEYS, f"{backend} raw entry", *entry_path
            )
            if "id" not in data:
                raise self.error("Raw entry must define 'id'", *entry_path)
            entry_id = self._identifier(data["id"], "Raw entry id", *entry_path, "id")
            if entry_id in seen:
                raise self.error(
                    f"Duplicate {backend} raw entry id '{entry_id}'",
                    *entry_path,
                    "id",
                )
            seen.add(entry_id)
            description = data.get("description")
            if description is not None and not isinstance(description, str):
                raise self.error(
                    "Raw entry description must be a string",
                    *entry_path,
                    "description",
                )
            code = data.get("code")
            if not isinstance(code, str):
                code_path = (*entry_path, "code") if "code" in data else entry_path
                raise self.error("Raw entry must define string 'code'", *code_path)
            entries.append(
                RawEntry(
                    id=entry_id,
                    code=_strip_final_newline(code),
                    description=description,
                    yaml_path=(_SECTION, *entry_path),
                )
            )
        return tuple(entries)


def _unsupported_raw_message(backend: str) -> str:
    if backend == "sva":
        return "verification.backends.sva.raw is not supported until the SVA backend is implemented"
    return f"verification.backends.{backend} does not accept raw code"


def _strip_final_newline(code: str) -> str:
    """Strip the one final newline added by a YAML block scalar."""
    if code.endswith("\r\n"):
        return code[:-2]
    if code.endswith("\n"):
        return code[:-1]
    return code


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)
