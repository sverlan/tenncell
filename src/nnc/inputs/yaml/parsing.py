"""YAML parsing helpers for TENNCell systems."""

from pathlib import Path

from ...parser import parse_expression
from ...parser.ast.value import FloatValue
from .errors import YamlLocatedError
from .locations import YamlLocationIndex
from .module_config import ModuleConfig


def parse_module_config(module_data: dict | None, source_path: Path) -> ModuleConfig:
    """Parse the shared module metadata block from YAML."""
    module_data = module_data or {}
    return ModuleConfig(
        name=module_data.get("name", source_path.stem),
        zero_reset_mode=module_data.get("zero_reset_mode", False),
        description=module_data.get("description"),
    )


def parse_constants(
    constants_data: dict | None,
    source_path: Path | None = None,
    locations: YamlLocationIndex | None = None,
) -> dict[str, FloatValue]:
    """Parse constant declarations and evaluate expression-valued entries."""
    constants: dict[str, FloatValue] = {}
    for key, value in (constants_data or {}).items():
        if isinstance(value, str):
            try:
                constants[key] = parse_expression(value, {}, constants, {}).evaluate()
            except Exception as e:
                raise YamlLocatedError(
                    f"Error evaluating constant '{key}':\n{e}",
                    locations.source_for("constants", key)
                    if locations is not None
                    else source_path,
                    locations.line_for("constants", key) if locations is not None else None,
                )
        else:
            constants[key] = FloatValue(value)
    return constants
