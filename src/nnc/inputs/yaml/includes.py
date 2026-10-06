"""YAML include expansion for TENNCell module fragments."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import YamlLocatedError
from .locations import YamlLocation, YamlLocationIndex, load_yaml_data_and_locations
from .resolution import resolve_path

_LIST_MERGE_PATHS: set[tuple[object, ...]] = {
    ("cells",),
    ("imports",),
    ("rules",),
    ("fsm",),
    ("verilog", "ports"),
    ("webots", "csv", "variables"),
}


@dataclass(slots=True)
class _IncludeAccumulator:
    """Effective YAML data plus merged path origins."""

    data: dict[str, Any]
    paths: dict[tuple[object, ...], YamlLocation]


def load_yaml_with_includes(
    source_path: Path,
    import_paths: list[Path] | None = None,
) -> tuple[dict[str, Any], YamlLocationIndex]:
    """Load a root YAML document and expand its ``module.include`` fragments."""
    import_paths = import_paths or []
    data, locations = load_yaml_data_and_locations(source_path)
    if not isinstance(data, dict):
        raise YamlLocatedError(
            "TENNCell YAML document must be a mapping",
            source_path,
            locations.first_line_under(),
        )
    _reject_top_level_include(data, source_path, locations)

    include_entries = _module_include_entries(data, source_path, locations)
    effective = _IncludeAccumulator({}, {})
    for include_index, include_entry in include_entries:
        try:
            include_path = resolve_path(include_entry, source_path, import_paths)
        except ValueError as e:
            raise YamlLocatedError(
                f"Could not resolve include '{include_entry}':\n{e}",
                source_path,
                locations.line_for("module", "include", include_index)
                or locations.line_for("module", "include"),
            ) from e
        include_data, include_locations = load_yaml_data_and_locations(include_path)
        if not isinstance(include_data, dict):
            raise YamlLocatedError(
                "Included YAML fragment must be a mapping",
                include_path,
                include_locations.first_line_under(),
            )
        if "module" in include_data:
            raise YamlLocatedError(
                "Included YAML fragment must not contain a module section",
                include_path,
                include_locations.line_for("module"),
            )
        _reject_top_level_include(include_data, include_path, include_locations)
        try:
            effective = _merge_yaml_documents(
                effective,
                include_data,
                include_locations,
            )
        except YamlLocatedError as e:
            raise YamlLocatedError(
                f"Error merging include '{include_entry}':\n{e}",
                source_path,
                locations.line_for("module", "include", include_index)
                or locations.line_for("module", "include"),
            ) from e

    root_data = _without_module_include(data)
    effective = _merge_yaml_documents(
        effective,
        root_data,
        locations,
    )
    return effective.data, YamlLocationIndex(source_path, effective.paths)


def _reject_top_level_include(
    data: dict[str, Any], source_path: Path, locations: YamlLocationIndex
) -> None:
    """Reject legacy-looking top-level include declarations."""
    if "include" in data:
        raise YamlLocatedError(
            "YAML includes must be declared as module.include",
            source_path,
            locations.line_for("include"),
        )


def _module_include_entries(
    data: dict[str, Any],
    source_path: Path,
    locations: YamlLocationIndex,
) -> list[tuple[int, str]]:
    """Return normalized include entries from the root module section."""
    module = data.get("module")
    if not isinstance(module, dict) or "include" not in module:
        return []
    raw_include = module["include"]
    if isinstance(raw_include, str):
        return [(0, raw_include)]
    if not isinstance(raw_include, list):
        raise YamlLocatedError(
            "module.include must be a string or list of strings",
            source_path,
            locations.line_for("module", "include"),
        )
    entries: list[tuple[int, str]] = []
    for index, item in enumerate(raw_include):
        if not isinstance(item, str):
            raise YamlLocatedError(
                "module.include entries must be strings",
                source_path,
                locations.line_for("module", "include", index)
                or locations.line_for("module", "include"),
            )
        entries.append((index, item))
    return entries


def _without_module_include(data: dict[str, Any]) -> dict[str, Any]:
    """Return a deep copy of root data without ``module.include``."""
    result = deepcopy(data)
    module = result.get("module")
    if isinstance(module, dict):
        module.pop("include", None)
        if not module:
            result.pop("module", None)
    return result


def _merge_yaml_documents(
    accumulator: _IncludeAccumulator,
    incoming: dict[str, Any],
    incoming_locations: YamlLocationIndex,
) -> _IncludeAccumulator:
    """Merge one YAML document into the effective data and location map."""
    merged_data, merged_paths = _merge_yaml_values(
        accumulator.data,
        incoming,
        path=(),
        left_paths=accumulator.paths,
        right_paths=incoming_locations.paths,
        right_prefix=(),
        right_document_path=(),
    )
    return _IncludeAccumulator(merged_data, merged_paths)


def _merge_yaml_values(
    left: Any,
    right: Any,
    *,
    path: tuple[object, ...],
    left_paths: dict[tuple[object, ...], YamlLocation],
    right_paths: dict[tuple[object, ...], YamlLocation],
    right_prefix: tuple[object, ...],
    right_document_path: tuple[object, ...],
) -> tuple[Any, dict[tuple[object, ...], YamlLocation]]:
    """Merge two YAML values and their path origins or raise on contradictions."""
    if isinstance(left, dict) and isinstance(right, dict):
        merged = deepcopy(left)
        merged_paths = dict(left_paths)
        for key, right_value in right.items():
            child_path = path + (key,)
            if key in merged:
                merged[key], merged_paths = _merge_yaml_values(
                    merged[key],
                    right_value,
                    path=child_path,
                    left_paths=merged_paths,
                    right_paths=right_paths,
                    right_prefix=child_path,
                    right_document_path=right_document_path + (key,),
                )
            else:
                merged[key] = deepcopy(right_value)
                _copy_location_subtree(
                    merged_paths,
                    right_paths,
                    right_document_path + (key,),
                    child_path,
                )
        return merged, merged_paths

    if isinstance(left, list) and isinstance(right, list) and path in _LIST_MERGE_PATHS:
        merged_paths = dict(left_paths)
        offset = len(left)
        for index, _ in enumerate(right):
            _copy_location_subtree(
                merged_paths,
                right_paths,
                right_document_path + (index,),
                path + (offset + index,),
            )
        return [*deepcopy(left), *deepcopy(right)], merged_paths

    if left == right:
        return deepcopy(left), dict(left_paths)

    location_path = path if path else ()
    location = right_paths.get(right_document_path) or right_paths.get(location_path)
    raise YamlLocatedError(
        f"Conflicting YAML include value at {'.'.join(str(item) for item in path)}",
        location.source_path if location is not None else None,
        location.line if location is not None else None,
    )


def _copy_location_subtree(
    target: dict[tuple[object, ...], YamlLocation],
    source: dict[tuple[object, ...], YamlLocation],
    source_prefix: tuple[object, ...],
    target_prefix: tuple[object, ...],
) -> None:
    """Copy source origins under one YAML path into another effective path."""
    for source_path, location in source.items():
        if len(source_path) < len(source_prefix):
            continue
        if source_path[: len(source_prefix)] != source_prefix:
            continue
        suffix = source_path[len(source_prefix) :]
        target[target_prefix + suffix] = location
