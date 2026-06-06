"""YAML loader error helpers for TENNCell."""

from __future__ import annotations

from pathlib import Path

from .locations import format_yaml_location


class YamlLocatedError(ValueError):
    """ValueError carrying YAML source location metadata."""

    def __init__(
        self,
        message: str,
        source_path: Path | None = None,
        line: int | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.source_path = source_path
        self.line = line

    def attach_location(
        self, source_path: Path | None = None, line: int | None = None
    ) -> "YamlLocatedError":
        """Update the stored location and return the error itself."""
        if source_path is not None:
            self.source_path = source_path
        if line is not None:
            self.line = line
        return self

    @property
    def location(self) -> str | None:
        """Return the formatted location prefix, if available."""
        if self.source_path is None:
            return None
        return format_yaml_location(self.source_path, self.line)

    def __str__(self) -> str:
        if self.location is None:
            return self.message
        return f"{self.location}: {self.message}"


def as_yaml_located_error(
    error: Exception,
    source_path: Path | None = None,
    line: int | None = None,
) -> YamlLocatedError:
    """Convert or annotate an exception with YAML location metadata."""
    if isinstance(error, YamlLocatedError):
        if error.source_path is None:
            error.attach_location(source_path, line)
        elif error.line is None and line is not None:
            error.attach_location(line=line)
        return error
    located_error = YamlLocatedError(str(error), source_path, line)
    located_error.__cause__ = error
    return located_error
