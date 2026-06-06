"""Source-location helpers for TENNCell YAML documents."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

from .lexical import sanitize_bang_prefixed_scalars


@dataclass(slots=True)
class YamlLocationIndex:
    """Path-to-line index for one YAML source file."""

    source_path: Path
    paths: dict[tuple[object, ...], int]

    def line_for(self, *path: object) -> int | None:
        """Return the 1-based line number for a YAML path, if known."""
        return self.paths.get(path)

    def first_line_under(self, *prefix: object) -> int | None:
        """Return the first known line number under a YAML path prefix."""
        for path, line in self.paths.items():
            if len(path) >= len(prefix) and path[: len(prefix)] == prefix:
                return line
        return None

    def error(self, message: str, *path: object) -> YamlLocatedError:
        """Build a located YAML error for this file and path."""
        from .errors import YamlLocatedError

        return YamlLocatedError(message, self.source_path, self.line_for(*path))


def _node_key(node: Node) -> object:
    """Convert a YAML node used as a mapping key into a hashable path element."""
    if isinstance(node, ScalarNode):
        return node.value
    return yaml.safe_load(yaml.serialize(node))


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
    node = yaml.compose(sanitized)
    data = yaml.safe_load(sanitized) or {}
    return data, YamlLocationIndex(source_path, collect_yaml_locations(node))


def format_yaml_location(source_path: Path, line: int | None) -> str:
    """Format a source location prefix for a YAML error message."""
    if line is None:
        return str(source_path)
    return f"{source_path}:{line}"
