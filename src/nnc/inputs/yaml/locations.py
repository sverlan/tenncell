"""Source-location helpers for TENNCell YAML documents."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from yaml.nodes import MappingNode, Node, SequenceNode

from .lexical import sanitize_bang_prefixed_scalars
from .yaml_schema import TenncellYamlLoader


@dataclass(slots=True)
class YamlLocation:
    """Physical YAML source location for one effective document path."""

    source_path: Path
    line: int | None


@dataclass(slots=True)
class YamlLocationIndex:
    """Path-to-source-location index for one effective YAML document."""

    source_path: Path
    paths: dict[tuple[object, ...], YamlLocation | int]

    def __post_init__(self) -> None:
        """Normalize legacy path-to-line dictionaries into location entries."""
        self.paths = {
            path: (
                location
                if isinstance(location, YamlLocation)
                else YamlLocation(self.source_path, location)
            )
            for path, location in self.paths.items()
        }

    def location_for(self, *path: object) -> YamlLocation | None:
        """Return the physical source location for a YAML path, if known."""
        return self.paths.get(path)

    def source_for(self, *path: object) -> Path:
        """Return the physical source file for a YAML path or the root fallback."""
        location = self.location_for(*path)
        if location is None:
            return self.source_path
        return location.source_path

    def line_for(self, *path: object) -> int | None:
        """Return the 1-based line number for a YAML path, if known."""
        location = self.location_for(*path)
        if location is None:
            return None
        return location.line

    def location_under(self, *prefix: object) -> YamlLocation | None:
        """Return the first known source location under a YAML path prefix."""
        for path, location in self.paths.items():
            if len(path) >= len(prefix) and path[: len(prefix)] == prefix:
                return location
        return None

    def first_line_under(self, *prefix: object) -> int | None:
        """Return the first known line number under a YAML path prefix."""
        location = self.location_under(*prefix)
        if location is None:
            return None
        return location.line

    def source_for_under(self, *prefix: object) -> Path:
        """Return the first known source file under a YAML path prefix."""
        location = self.location_under(*prefix)
        if location is None:
            return self.source_path
        return location.source_path

    def error(self, message: str, *path: object) -> YamlLocatedError:
        """Build a located YAML error for this file and path."""
        from .errors import YamlLocatedError

        location = self.location_for(*path) or self.location_under(*path)
        if location is None:
            return YamlLocatedError(message, self.source_path, None)
        return YamlLocatedError(message, location.source_path, location.line)


def _node_key(node: Node) -> object:
    """Convert a YAML mapping-key node into the same value the loaded data uses.

    Keys are resolved with the TENNCell loader, so ``010``, ``true`` and ``null``
    index locations as ``10``, ``True`` and ``None``, matching the parsed data.
    """
    loader = TenncellYamlLoader("")
    try:
        return loader.construct_object(node, deep=True)
    finally:
        loader.dispose()


def collect_yaml_locations(node: Node | None) -> dict[tuple[object, ...], int]:
    """Collect 1-based line numbers for YAML values reachable from a node tree."""
    locations: dict[tuple[object, ...], int] = {}

    def visit(current: Node, path: tuple[object, ...]) -> None:
        if isinstance(current, MappingNode):
            for key_node, value_node in current.value:
                key = _node_key(key_node)
                child_path = path + (key,)
                locations[child_path] = value_node.start_mark.line + 1
                if isinstance(value_node, (MappingNode, SequenceNode)):
                    visit(value_node, child_path)
            return

        if isinstance(current, SequenceNode):
            for index, item in enumerate(current.value):
                child_path = path + (index,)
                locations[child_path] = item.start_mark.line + 1
                if isinstance(item, (MappingNode, SequenceNode)):
                    visit(item, child_path)
            return

    if node is not None:
        visit(node, ())
    return locations


def load_yaml_data_and_locations(
    source_path: Path,
) -> tuple[dict[str, Any], YamlLocationIndex]:
    """Load YAML content and collect path-to-line metadata for the document."""
    with source_path.open("r", encoding="utf-8") as file:
        sanitized = sanitize_bang_prefixed_scalars(file)
    node = yaml.compose(sanitized, Loader=TenncellYamlLoader)
    data = yaml.load(sanitized, Loader=TenncellYamlLoader) or {}
    return data, YamlLocationIndex(source_path, collect_yaml_locations(node))


def format_yaml_location(source_path: Path, line: int | None) -> str:
    """Format a source location prefix for a YAML error message."""
    if line is None:
        return str(source_path)
    return f"{source_path}:{line}"
