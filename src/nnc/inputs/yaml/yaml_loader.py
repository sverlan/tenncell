from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from ...model.cell import Cell
from ...parser import parse_variable_assignment
from ...parser.ast.value import FloatValue
from ...parser.ast.variable import Variable
from .errors import as_yaml_located_error
from .includes import load_yaml_with_includes
from .locations import YamlLocationIndex
from .lowering import (
    ExpandedRepeatItem,
    build_state_constants,
    expand_repeat_items,
    lower_fsm_rules,
    lower_rule_items,
    register_initial_declarations,
)
from .module_config import ImportConfig
from .parsing import parse_constants, parse_module_config
from .raw_model import RawYamlDocument
from .resolution import parse_reference_expr, resolve_path

if TYPE_CHECKING:  # pragma: no cover
    from ...model.system import NncSystem


def _load_raw_yaml_document(
    file_path: str,
    import_paths: list[str] | None = None,
) -> RawYamlDocument:
    """Load and normalize a TENNCell YAML file into a raw document."""
    source_path = Path(file_path).resolve()
    import_paths_resolved = [Path(path).resolve() for path in (import_paths or [])]
    data, locations = load_yaml_with_includes(source_path, import_paths_resolved)
    return RawYamlDocument.from_data(source_path, data, locations)

def _build_system_from_raw_document(
    system_cls: type["NncSystem"],
    raw_document: RawYamlDocument,
    import_paths: list[str] | None = None,
    _loading_stack: list[Path] | None = None,
    _system_cache: dict[Path, "NncSystem"] | None = None,
    _raw_data_cache: dict[Path, dict] | None = None,
):
    """Resolve a raw TENNCell document into the in-memory system model."""
    source_path = raw_document.source_path
    import_paths_resolved = [Path(path).resolve() for path in (import_paths or [])]
    loading_stack = list(_loading_stack or [])
    system_cache = _system_cache if _system_cache is not None else {}
    raw_data_cache = _raw_data_cache if _raw_data_cache is not None else {}

    if source_path in loading_stack:
        cycle = " -> ".join(str(item) for item in [*loading_stack, source_path])
        raise ValueError(f"Import cycle detected: {cycle}")
    if source_path in system_cache:
        return system_cache[source_path]

    nnc = system_cls()
    nnc.source_path = source_path
    nnc.source_locations = raw_document.locations
    loading_stack.append(source_path)
    system_cache[source_path] = nnc
    raw_data_cache[source_path] = raw_document.data

    try:
        nnc.module_config = parse_module_config(raw_document.module, source_path)
    except Exception as e:
        raise as_yaml_located_error(
            e, source_path, raw_document.locations.line_for("module")
        )
    nnc.metadata = {}
    if nnc.module_config.description is not None:
        nnc.metadata["description"] = nnc.module_config.description
    try:
        nnc.constants = parse_constants(
            raw_document.constants, source_path, raw_document.locations
        )
    except Exception as e:
        raise as_yaml_located_error(
            e, source_path, raw_document.locations.line_for("constants")
        )

    variables: dict[str, Variable] = {}
    initial_declarations: dict[str, tuple[int, int]] = {}

    for cell_index, cell_data in enumerate(raw_document.cells):
        if isinstance(cell_data, dict) and "repeat" in cell_data:
            raise raw_document.locations.error(
                "repeat is not supported in top-level cells", "cells", cell_index
            )
        cell_id = cell_data.get("id")
        if not isinstance(cell_id, int):
            raise raw_document.locations.error("Cell id must be an integer", "cells", cell_index)
        contents = {}
        expanded_contents = expand_repeat_items(
            cell_data.get("contents", []),
            raw_document.locations,
            ("cells", cell_index, "contents"),
        )
        for content_index, expanded_item in enumerate(expanded_contents):
            variable_data = expanded_item.value
            if isinstance(variable_data, dict) and "name" in variable_data:
                variable_name = variable_data.get("name")
                if not isinstance(variable_name, str):
                    raise raw_document.locations.error(
                        "Variable name must be a string",
                        *expanded_item.origin_path,
                    )
                variable_value = variable_data.get("value")
                if not isinstance(variable_value, int | float | str):
                    raise raw_document.locations.error(
                        "Variable value must be a number or string",
                        *expanded_item.origin_path,
                    )
                variable = variables.get(
                    variable_name, Variable(variable_name, FloatValue(variable_value))
                )
                try:
                    register_initial_declarations(
                        initial_declarations,
                        [variable_name],
                        cell_index,
                        content_index,
                    )
                except ValueError as e:
                    raise raw_document.locations.error(
                        str(e), *expanded_item.origin_path
                    ) from e
                variables[variable_name] = variable
                contents[variable_name] = variable
            else:
                try:
                    parsed_variables = cast(
                        dict[str, Variable],
                        parse_variable_assignment(
                            variable_data, variables, nnc.constants, nnc.aliases
                        ),
                    )
                except Exception as e:
                    raise as_yaml_located_error(
                        raw_document.locations.error(
                            f"Error parsing variable assignment '{variable_data}':\n{e}",
                            *expanded_item.origin_path,
                        )
                    )
                try:
                    register_initial_declarations(
                        initial_declarations,
                        parsed_variables,
                        cell_index,
                        content_index,
                    )
                except ValueError as e:
                    raise raw_document.locations.error(
                        str(e), *expanded_item.origin_path
                    ) from e
                contents.update(parsed_variables)
                variables.update(parsed_variables)
        cell = Cell(cell_id, contents)
        nnc.add_cell(cell)

        expanded_inputs = expand_repeat_items(
            cell_data.get("input", []),
            raw_document.locations,
            ("cells", cell_index, "input"),
        )
        for expanded_input in expanded_inputs:
            variable_name = expanded_input.value
            try:
                nnc.input_variables[variable_name] = variables[variable_name]
            except KeyError as e:
                raise raw_document.locations.error(
                    f"Input variable {variable_name} not defined",
                    *expanded_input.origin_path,
                ) from e
        expanded_outputs = expand_repeat_items(
            cell_data.get("output", []),
            raw_document.locations,
            ("cells", cell_index, "output"),
        )
        for expanded_output in expanded_outputs:
            variable_name = expanded_output.value
            try:
                nnc.output_variables[variable_name] = variables[variable_name]
            except KeyError as e:
                raise raw_document.locations.error(
                    f"Output variable {variable_name} not defined",
                    *expanded_output.origin_path,
                ) from e

    nnc.variables = variables

    try:
        fsm_constants, fsm_initializers = build_state_constants(
            raw_document.fsm, variables, nnc.constants
        )
    except Exception as e:
        raise as_yaml_located_error(
            raw_document.locations.error(
                f"Error building FSM state constants:\n{e}", "fsm"
            )
        )
    try:
        for variable_name, constant_name in fsm_initializers:
            variables[variable_name].value = nnc.constants[constant_name]
    except Exception as e:
        raise as_yaml_located_error(
            raw_document.locations.error(
                f"Error applying FSM initializers:\n{e}", "fsm"
            )
        )

    for import_data in raw_document.imports:
        alias = import_data["as"]
        import_path = resolve_path(
            import_data["module"], source_path, import_paths_resolved
        )
        try:
            imported_system = system_cls.from_yaml(
                str(import_path),
                import_paths=[str(path) for path in import_paths_resolved],
                _loading_stack=loading_stack,
                _system_cache=system_cache,
                _raw_data_cache=raw_data_cache,
            )
        except Exception as e:
            raise as_yaml_located_error(e)
        nnc.imports.append(
            ImportConfig(
                module=str(import_path),
                alias=alias,
                connections=import_data.get("connections", {}),
                system=imported_system,
            )
        )

    for alias_name, target in (raw_document.aliases or {}).items():
        try:
            nnc.aliases[alias_name] = parse_reference_expr(
                target, variables, nnc.constants, nnc.aliases
            )
        except Exception as e:
            raise as_yaml_located_error(
                raw_document.locations.error(
                    f"Error parsing alias '{alias_name}':\n{e}",
                    "aliases",
                    alias_name,
                )
            )

    try:
        for expanded_rule in expand_repeat_items(
            raw_document.rules,
            raw_document.locations,
            ("rules",),
        ):
            for rule in _lower_expanded_rule_item(
                expanded_rule,
                variables,
                nnc.constants,
                nnc.aliases,
                raw_document.locations,
            ):
                nnc.add_rule(rule)
        for rule in lower_fsm_rules(
            raw_document.fsm, variables, nnc.constants, nnc.aliases, fsm_constants
        ):
            nnc.add_rule(rule)
    except Exception as e:
        raise as_yaml_located_error(
            raw_document.locations.error(f"Error lowering YAML rules:\n{e}", "rules")
        )

    try:
        nnc.validate_references()
    except Exception as e:
        raise as_yaml_located_error(
            raw_document.locations.error(
                f"Error validating YAML references:\n{e}", "imports"
            )
        )
    loading_stack.pop()
    return nnc


def _lower_expanded_rule_item(
    expanded_rule: ExpandedRepeatItem,
    variables: dict[str, Variable],
    constants: dict[str, FloatValue],
    aliases,
    locations: YamlLocationIndex,
):
    """Lower one expanded rule item and report generated errors at its origin."""
    try:
        return lower_rule_items(
            [expanded_rule.value],
            variables,
            constants,
            aliases,
        )
    except Exception as e:
        raise locations.error(
            f"Error lowering YAML rules:\n{e}", *expanded_rule.origin_path
        ) from e


def load_system_from_yaml(
    system_cls: type["NncSystem"],
    file_path: str,
    import_paths: list[str] | None = None,
    _loading_stack: list[Path] | None = None,
    _system_cache: dict[Path, "NncSystem"] | None = None,
    _raw_data_cache: dict[Path, dict] | None = None,
):
    """Load a TENNCell system from YAML and lower it into the in-memory model."""
    raw_document = _load_raw_yaml_document(file_path, import_paths)
    return _build_system_from_raw_document(
        system_cls,
        raw_document,
        import_paths=import_paths,
        _loading_stack=_loading_stack,
        _system_cache=_system_cache,
        _raw_data_cache=_raw_data_cache,
    )
