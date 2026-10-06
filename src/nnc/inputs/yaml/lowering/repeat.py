"""List-only repeat expansion for TENNCell YAML sugar."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from ..errors import YamlLocatedError
from ..locations import YamlLocationIndex


_VAR_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_PLACEHOLDER_RE = re.compile(r"\$\{([^}]+)\}")
_PLACEHOLDER_BODY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)(?:([+-])([1-9][0-9]*))?$")


@dataclass(slots=True)
class ExpandedRepeatItem:
    """A YAML list item and the original path used for error reporting."""

    value: Any
    origin_path: tuple[object, ...]


def expand_repeat_items(
    items: object,
    locations: YamlLocationIndex,
    path: tuple[object, ...],
) -> list[ExpandedRepeatItem]:
    """Expand list-item repeat sugar and keep origin paths for diagnostics."""
    if items is None:
        return []
    if not isinstance(items, list):
        raise _error(locations, "repeat expansion expects a list", path)
    return _expand_items(items, locations, path, {})


def unwrap_expanded_items(items: list[ExpandedRepeatItem]) -> list[Any]:
    """Return raw YAML values from expanded items."""
    return [item.value for item in items]


def _expand_items(
    items: list[Any],
    locations: YamlLocationIndex,
    path: tuple[object, ...],
    bindings: dict[str, int],
) -> list[ExpandedRepeatItem]:
    expanded: list[ExpandedRepeatItem] = []
    for index, item in enumerate(items):
        item_path = (*path, index)
        if _is_repeat_item(item):
            expanded.extend(_expand_repeat_item(item["repeat"], locations, item_path, bindings))
        else:
            expanded.append(ExpandedRepeatItem(_substitute(item, bindings, locations, item_path), item_path))
    return expanded


def _is_repeat_item(item: object) -> bool:
    return isinstance(item, dict) and set(item.keys()) == {"repeat"}


def _expand_repeat_item(
    repeat_data: object,
    locations: YamlLocationIndex,
    repeat_path: tuple[object, ...],
    bindings: dict[str, int],
) -> list[ExpandedRepeatItem]:
    if not isinstance(repeat_data, dict):
        raise _error(locations, "repeat item must be a mapping", repeat_path)
    allowed_keys = {"var", "range", "body"}
    unknown_keys = set(repeat_data.keys()) - allowed_keys
    if unknown_keys:
        unknown = sorted(unknown_keys)[0]
        raise _error(locations, f"repeat has unsupported field '{unknown}'", (*repeat_path, "repeat", unknown))

    var_name = repeat_data.get("var")
    if not isinstance(var_name, str) or not _VAR_RE.fullmatch(var_name):
        raise _error(locations, "repeat.var must be a valid placeholder name", (*repeat_path, "repeat", "var"))
    if var_name in bindings:
        raise _error(locations, f"repeat variable '{var_name}' shadows an active repeat variable", (*repeat_path, "repeat", "var"))

    values = _range_values(repeat_data.get("range"), locations, (*repeat_path, "repeat", "range"))
    body = repeat_data.get("body")
    if not isinstance(body, list):
        raise _error(locations, "repeat.body must be a list", (*repeat_path, "repeat", "body"))

    expanded: list[ExpandedRepeatItem] = []
    for value in values:
        next_bindings = {**bindings, var_name: value}
        for item in _expand_items(
            body,
            locations,
            (*repeat_path, "repeat", "body"),
            next_bindings,
        ):
            expanded.append(ExpandedRepeatItem(item.value, repeat_path))
    return expanded


def _range_values(
    raw_range: object,
    locations: YamlLocationIndex,
    path: tuple[object, ...],
) -> list[int]:
    if not isinstance(raw_range, list) or len(raw_range) not in {2, 3}:
        raise _error(locations, "repeat.range must be [start, end] or [start, end, step]", path)
    if not all(isinstance(value, int) and not isinstance(value, bool) for value in raw_range):
        raise _error(locations, "repeat.range values must be integers", path)

    start = raw_range[0]
    end = raw_range[1]
    step = raw_range[2] if len(raw_range) == 3 else 1
    if step == 0:
        raise _error(locations, "repeat.range step cannot be zero", path)
    if start < end and step < 0:
        raise _error(locations, "repeat.range step must be positive for ascending ranges", path)
    if start > end and step > 0:
        raise _error(locations, "repeat.range step must be negative for descending ranges", path)
    if (end - start) % step != 0:
        raise _error(locations, "repeat.range end must be reached exactly by step", path)
    return list(range(start, end + (1 if step > 0 else -1), step))


def _substitute(
    value: Any,
    bindings: dict[str, int],
    locations: YamlLocationIndex,
    path: tuple[object, ...],
) -> Any:
    if isinstance(value, str):
        return _substitute_string(value, bindings, locations, path)
    if isinstance(value, list):
        return [
            _substitute(item, bindings, locations, (*path, index))
            for index, item in enumerate(value)
        ]
    if isinstance(value, dict):
        return {
            _substitute(key, bindings, locations, (*path, key)): _substitute(
                item, bindings, locations, (*path, key)
            )
            for key, item in value.items()
        }
    return value


def _substitute_string(
    value: str,
    bindings: dict[str, int],
    locations: YamlLocationIndex,
    path: tuple[object, ...],
) -> str | int:
    exact_match = _PLACEHOLDER_RE.fullmatch(value)
    if exact_match is not None:
        return _evaluate_placeholder(exact_match.group(1), bindings, locations, path)

    def replace(match: re.Match[str]) -> str:
        return str(_evaluate_placeholder(match.group(1), bindings, locations, path))

    return _PLACEHOLDER_RE.sub(replace, value)


def _evaluate_placeholder(
    expression: str,
    bindings: dict[str, int],
    locations: YamlLocationIndex,
    path: tuple[object, ...],
) -> int:
    match = _PLACEHOLDER_BODY_RE.fullmatch(expression)
    if match is None:
        raise _error(locations, f"Invalid repeat placeholder '${{{expression}}}'", path)
    name, sign, offset_text = match.groups()
    if name not in bindings:
        raise _error(locations, f"Unknown repeat placeholder '{name}'", path)
    value = bindings[name]
    if offset_text is None:
        return value
    offset = int(offset_text)
    return value + offset if sign == "+" else value - offset


def _error(
    locations: YamlLocationIndex,
    message: str,
    path: tuple[object, ...],
) -> YamlLocatedError:
    return locations.error(message, *path)
