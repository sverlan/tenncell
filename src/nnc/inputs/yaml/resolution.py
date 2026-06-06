"""Path and external header resolution helpers for TENNCell YAML loading."""

from pathlib import Path

from ...parser.ast import (
    ConstantExpression,
    Expression,
    ReferenceExpression,
    VariableExpression,
)
from ...parser.ast.value import FloatValue
from ...parser.ast.variable import Variable


def resolve_path(path_value: str, source_path: Path, import_paths: list[Path]) -> Path:
    """Resolve a relative YAML path against the source file and import paths."""
    candidate = (source_path.parent / path_value).resolve()
    if candidate.exists():
        return candidate
    for import_path in import_paths:
        candidate = (import_path / path_value).resolve()
        if candidate.exists():
            return candidate
    searched = [str(source_path.parent / path_value)] + [
        str(import_path / path_value) for import_path in import_paths
    ]
    raise ValueError(
        f"Could not resolve import '{path_value}'. Tried: {', '.join(searched)}"
    )


def parse_reference_expr(
    reference_value: str,
    variables: dict[str, Variable],
    constants: dict[str, FloatValue],
    aliases: dict[str, Expression],
) -> Expression:
    """Parse a reference string into the appropriate TENNCell expression object."""
    if "." in reference_value:
        fsm_constant_name = reference_value.replace(".", "__")
        if fsm_constant_name in constants:
            return ConstantExpression(constants[fsm_constant_name])
    if "." in reference_value:
        return ReferenceExpression(reference_value.split("."))
    if reference_value in aliases:
        return aliases[reference_value]
    if reference_value in constants:
        return ConstantExpression(constants[reference_value])
    if reference_value in variables:
        return VariableExpression(variables[reference_value])
    raise ValueError(f"Unknown reference '{reference_value}'")
