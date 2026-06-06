"""Lexical preprocessing helpers for TENNCell YAML loading."""

from __future__ import annotations

import json
from collections.abc import Iterable


def _split_comment(line: str) -> tuple[str, str]:
    """Split a YAML line into content and an inline comment."""
    line = line.rstrip("\r\n")
    in_single = False
    in_double = False
    for index, char in enumerate(line):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double:
            if index == 0 or line[index - 1].isspace():
                return line[:index], line[index:]
    return line, ""


def _quote_bang_scalar(content: str) -> str:
    """Quote an unquoted scalar that starts with a bang."""
    if not content:
        return content
    prefix = ""
    value = content
    if ":" in content:
        prefix, value = content.split(":", 1)
        if not value.startswith((" ", "\t")):
            return content
        prefix = f"{prefix}: "
        value = value.lstrip()
    elif content.lstrip().startswith("- "):
        leading = len(content) - len(content.lstrip())
        prefix = content[:leading] + "- "
        value = content[leading + 2 :].lstrip()
    else:
        return content

    if not value.startswith("!"):
        return content
    return f"{prefix}{json.dumps(value)}"


def sanitize_bang_prefixed_scalars(lines: Iterable[str]) -> str:
    """Quote plain YAML scalars that start with ``!``.

    PyYAML interprets bare ``!name`` values as tags. TENNCell expressions use
    ``!`` as a boolean operator, so plain scalars that start with ``!`` must be
    converted to quoted strings before the YAML parser sees them.
    """
    sanitized_lines: list[str] = []
    for line in lines:
        content, comment = _split_comment(line)
        sanitized_lines.append(_quote_bang_scalar(content) + comment)
    return "\n".join(sanitized_lines)
