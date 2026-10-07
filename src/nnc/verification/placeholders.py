"""Tokenizer for ``${name}`` placeholders in raw verification code."""

from __future__ import annotations

import re
from dataclasses import dataclass

_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?")


class TemplateError(ValueError):
    """Raised when raw code contains a malformed placeholder."""


@dataclass(frozen=True, slots=True)
class TextSegment:
    """Literal raw text passed through unchanged."""

    text: str


@dataclass(frozen=True, slots=True)
class Placeholder:
    """One ``${name}`` reference and its character offset in the raw code."""

    name: str
    offset: int


Segment = TextSegment | Placeholder


def parse_template(code: str) -> tuple[Segment, ...]:
    """Split raw code into literal text and ``${name}`` placeholders.

    ``$${`` produces a literal ``${``. Names are identifiers, optionally followed
    by one ``.member`` part.

    Args:
        code: Raw backend code.

    Returns:
        Segments in source order; adjacent literal text is merged.

    Raises:
        TemplateError: If a placeholder is unclosed, empty, or has an invalid name.
    """
    segments: list[Segment] = []
    text: list[str] = []
    index = 0
    while index < len(code):
        if code.startswith("$${", index):
            text.append("${")
            index += 3
            continue
        if code.startswith("${", index):
            end = code.find("}", index + 2)
            if end == -1:
                raise TemplateError(f"Unclosed placeholder at offset {index}")
            name = code[index + 2 : end]
            if not name:
                raise TemplateError(f"Empty placeholder at offset {index}")
            if not _NAME.fullmatch(name):
                raise TemplateError(
                    f"Invalid placeholder name '{name}' at offset {index}"
                )
            if text:
                segments.append(TextSegment("".join(text)))
                text = []
            segments.append(Placeholder(name, index))
            index = end + 1
            continue
        text.append(code[index])
        index += 1
    if text:
        segments.append(TextSegment("".join(text)))
    return tuple(segments)
