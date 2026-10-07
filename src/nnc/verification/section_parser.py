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
    BackendSection,
    InputEnvironment,
    PropertyStub,
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
                # Locations are indexed by the key's source text, which may not
                # match str(name) (e.g. `true`, `0x1`); fall back to the section.
                key_path: tuple[str, ...] = ("environment", str(name))
                if self.context.locations.location_for(_SECTION, *key_path) is None:
                    key_path = ("environment",)
                raise self.error(
                    f"verification.environment key '{name}' must be an input variable name",
                    *key_path,
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
        message = f"verification.environment.{name}.range must be [lo, hi] with lo <= hi"
        if not isinstance(raw, list) or len(raw) != 2:
            raise self.error(message, *path)
        if not all(_is_number(value) for value in raw):
            raise self.error(message, *path)
        lo, hi = float(raw[0]), float(raw[1])
        if lo > hi:
            raise self.error(message, *path)
        return lo, hi

    def _properties(self, raw: object) -> tuple[PropertyStub, ...]:
        if raw is None:
            return ()
        if not isinstance(raw, list):
            raise self.error("verification.properties must be a list", "properties")
        stubs: list[PropertyStub] = []
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
            stubs.append(
                PropertyStub(
                    id=property_id,
                    targets=self._targets(entry.get("targets"), *path, "targets"),
                    yaml_path=(_SECTION, *path),
                )
            )
        return tuple(stubs)

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
        data = self._mapping(
            raw, "verification.backends must be a mapping", "backends"
        )
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
