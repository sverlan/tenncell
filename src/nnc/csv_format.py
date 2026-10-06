"""Shared CSV formatting options for TENNCell tools and backends."""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Real


@dataclass(slots=True)
class CsvFormatConfig:
    """Describe common CSV parsing and output formatting options."""

    delimiter: str = ","
    precision: int | None = None
    include_initial: bool = False


def validate_csv_delimiter(value: object, *, field_name: str = "CSV delimiter") -> str:
    """Return a validated CSV delimiter string.

    Args:
        value: Raw delimiter value.
        field_name: Name used in validation errors.

    Returns:
        The validated delimiter.

    Raises:
        ValueError: If the delimiter is not a non-empty string.
    """
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def validate_csv_precision(
    value: object, *, field_name: str = "CSV precision"
) -> int | None:
    """Return a validated CSV precision value.

    Args:
        value: Raw precision value.
        field_name: Name used in validation errors.

    Returns:
        ``None`` or a non-negative integer precision.

    Raises:
        ValueError: If the precision is not ``None`` or a non-negative integer.
    """
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer or null")
    return value


def format_csv_value(value: object, precision: int | None = None) -> str:
    """Format one CSV value according to the shared TENNCell CSV contract."""
    numeric_value = _csv_numeric_value(value)
    if precision is not None and numeric_value is not None:
        return f"{numeric_value:.{precision}f}"
    return str(value)


def _csv_numeric_value(value: object) -> Real | None:
    """Return a plain numeric value when CSV precision can be applied."""
    if isinstance(value, Real) and not isinstance(value, bool):
        return value
    inner_value = getattr(value, "value", None)
    if isinstance(inner_value, Real) and not isinstance(inner_value, bool):
        return inner_value
    return None
