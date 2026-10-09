from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from .cell import Cell
from ..inputs.yaml.module_config import ImportConfig, ModuleConfig
from ..inputs.yaml.locations import YamlLocationIndex
from ..parser.ast import (
    BooleanExpression,
    Expression,
    ReferenceExpression,
    VariableExpression,
)
from ..parser.ast.variable import Variable
from ..parser.ast.value import FloatValue
from ..parser.ast.value.math_functions import MathFunctions
from .evaluation import evaluate_boolean, evaluate_expression
from .rule import Rule
from ..inputs.yaml.yaml_loader import load_system_from_yaml


@dataclass(slots=True)
class ResolvedReference:
    """Resolved reference metadata used by backends and validation.

    Args:
        kind: Reference kind used by backends, such as ``import``.
        path: Canonical string path for the resolved reference.

    Validation assumptions:
        Backends use this metadata after model validation. ``kind`` and
        ``path`` are expected to describe a reference that is already known to
        be legal in the current TENNCell system.
    """

    kind: str
    path: str


class NncSystem:
    """In-memory TENNCell model loaded from YAML or constructed programmatically.

    The system stores cells, rules, constants, aliases, and import metadata.
    Transformers and the runtime simulator consume this model directly.
    """

    cells: list[Cell]
    rules: list[Rule]
    variables: dict[str, Variable]
    input_variables: dict[str, Variable]
    output_variables: dict[str, Variable]

    def __init__(self):
        """Create an empty TENNCell system with default module metadata."""
        self.cells = []
        self.rules = []
        self.variables = {}
        self.input_variables = {}
        self.output_variables = {}
        self.module_config = ModuleConfig(name="nnc")
        self.constants: dict[str, FloatValue] = {}
        self.aliases: dict[str, Expression] = {}
        self.imports: list[ImportConfig] = []
        self.source_path: Path | None = None
        self.source_locations: YamlLocationIndex | None = None
        self.metadata: dict[str, str] = {}

    def add_cell(self, cell: Cell):
        """Add a cell and register its variables in the system namespace.

        Args:
            cell: Cell to append to the system.
        """
        self.cells.append(cell)
        self.variables.update(cell.contents)

    def add_rule(self, rule: Rule):
        """Append a lowered rule to the system.

        Args:
            rule: Lowered rule to append.
        """
        self.rules.append(rule)

    def get_variable(self, variable_name):
        """Return a variable by name, or ``None`` when it does not exist.

        Args:
            variable_name: Variable name to resolve.
        """
        return self.variables.get(variable_name, None)

    def _resolve_runtime_reference(self, reference: str) -> FloatValue:
        """Resolve an import reference at runtime for simulation steps.

        Args:
            reference: Qualified reference such as ``sensor0.level``.
        """
        fsm_constant_name = reference.replace(".", "__")
        if fsm_constant_name in self.constants:
            return cast(FloatValue, self.constants[fsm_constant_name])
        head, _, tail = reference.partition(".")

        for item in self.imports:
            if item.alias == head:
                if item.system is None:
                    raise ValueError(f"Import '{head}' is not resolved")
                variable = item.system.variables.get(tail)
                if variable is None:
                    raise ValueError(f"Unknown imported reference '{reference}'")
                return cast(FloatValue, variable.value)

        raise ValueError(f"Unknown runtime reference '{reference}'")

    def variable_value(self, node: VariableExpression) -> FloatValue:
        """Return a variable's current runtime value (evaluation context)."""
        return cast(FloatValue, node.variable.value)

    def reference_value(self, reference: str) -> FloatValue:
        """Return a qualified reference's runtime value (evaluation context)."""
        return cast(FloatValue, self._resolve_runtime_reference(reference))

    def call_function(self, name: str, arguments: list[float]) -> FloatValue:
        """Call a registered TENNCell function (evaluation context)."""
        return FloatValue(MathFunctions.evaluate(name, arguments))

    def _evaluate_expression(self, node: Expression) -> FloatValue:
        """Evaluate a TENNCell expression against the current runtime state.

        Args:
            node: TENNCell expression AST node.
        """
        return evaluate_expression(node, self)

    def _evaluate_boolean(self, node: BooleanExpression) -> bool:
        """Evaluate a TENNCell boolean expression against the current runtime state.

        Args:
            node: TENNCell boolean AST node.
        """
        return evaluate_boolean(node, self)

    def _direct_import_step_order(self) -> list[ImportConfig]:
        """Return imports in dependency order for a single simulation step."""
        alias_map = {item.alias: item for item in self.imports}
        dependency_map: dict[str, set[str]] = {alias: set() for alias in alias_map}
        for item in self.imports:
            for connection_ref in item.connections.values():
                if "." not in connection_ref:
                    continue
                head, _, _ = connection_ref.partition(".")
                if head in alias_map:
                    dependency_map[item.alias].add(head)

        ordered: list[ImportConfig] = []
        temp_mark: set[str] = set()
        perm_mark: set[str] = set()

        def visit(alias: str):
            if alias in perm_mark:
                return
            if alias in temp_mark:
                raise ValueError(
                    f"Import connection cycle detected in module '{self.module_config.name}'"
                )
            temp_mark.add(alias)
            for dep in sorted(dependency_map[alias]):
                visit(dep)
            temp_mark.remove(alias)
            perm_mark.add(alias)
            ordered.append(alias_map[alias])

        for alias in sorted(alias_map):
            visit(alias)
        return ordered

    def _build_import_inputs(self, item: ImportConfig) -> dict[str, float]:
        """Build the input mapping for a directly imported TENNCell module.

        Args:
            item: Import configuration for the child system.
        """
        assert item.system is not None
        inputs: dict[str, float] = {}
        for input_name in item.system.input_variables.keys():
            reference = item.connections.get(input_name)
            if reference is None:
                inputs[input_name] = 0.0
                continue
            if "." in reference:
                inputs[input_name] = self._resolve_runtime_reference(reference).value
            elif reference in self.variables:
                inputs[input_name] = self.variables[reference].value.value
            elif reference in self.constants:
                inputs[input_name] = self.constants[reference].value
            else:
                inputs[input_name] = float(reference)
        return inputs

    def get_variables(self) -> dict[str, FloatValue]:
        """Return the current variable values keyed by variable name."""
        return {
            name: cast(FloatValue, variable.value)
            for name, variable in self.variables.items()
        }

    def step(self, inputs: dict[str, float] | None = None):
        """Advance the system by one step and return declared outputs.

        Args:
            inputs: Optional mapping of input variable names to numeric values.
        """
        if inputs is not None:
            for input_name in self.input_variables.keys():
                if input_name not in inputs:
                    raise ValueError(
                        f"Input variable {input_name} is required but not provided"
                    )
                self.input_variables[input_name].value = FloatValue(inputs[input_name])

        for item in self._direct_import_step_order():
            assert item.system is not None
            item.system.step(self._build_import_inputs(item))

        production_values: dict[Rule, FloatValue] = {}
        used_vars: list[Variable] = []
        for rule in self.rules:
            if self._evaluate_boolean(rule.guard):
                production_values[rule] = self._evaluate_expression(rule.producer)
                if not self.module_config.zero_reset_mode:
                    used_vars.extend(rule.vars.values())

        if self.module_config.zero_reset_mode:
            input_names = set(self.input_variables.keys())
            for name, variable in self.variables.items():
                if name not in input_names:
                    variable.value = FloatValue(0.0)
        else:
            used_vars_set = set(used_vars)
            for variable in used_vars_set:
                variable.value = FloatValue(0.0)

        for rule in production_values:
            rule.consumer.value = cast(
                FloatValue,
                cast(FloatValue, rule.consumer.value) + production_values[rule],
            )

        return {
            name: variable.value.value
            for name, variable in self.output_variables.items()
        }

    @staticmethod
    def _iter_references(node):
        """Yield qualified references reachable from an AST node."""
        if isinstance(node, ReferenceExpression):
            yield ".".join(node.parts)
            return
        for attr in ("left", "right", "expression"):
            child = getattr(node, attr, None)
            if child is not None:
                yield from NncSystem._iter_references(child)
        for arg in getattr(node, "arguments", []):
            yield from NncSystem._iter_references(arg)

    def _validate_reference(self, reference: str):
        """Validate one qualified reference against the current model.

        Args:
            reference: Qualified reference string.
        """
        head, _, tail = reference.partition(".")
        if not tail:
            return
        if reference.replace(".", "__") in self.constants:
            return

        import_map = {item.alias: item for item in self.imports}
        if head in import_map:
            imported = import_map[head].system
            if imported is None:
                raise ValueError(f"Import '{head}' is not resolved")
            allowed = set(imported.input_variables.keys()) | set(
                imported.output_variables.keys()
            )
            if tail not in allowed:
                raise ValueError(
                    f"Reference '{reference}' must target an imported module input or output"
                )
            return

        raise ValueError(
            f"Reference '{reference}' must target an imported module input or output"
        )

    def _validate_alias_reference(self, reference: str):
        """Validate one alias target against the current model.

        Alias targets remain TENNCell-level names: local variables, constants, or
        imported module references. Top-level Verilog names are not legal
        alias targets.
        """
        head, _, tail = reference.partition(".")
        if not tail:
            return
        if reference.replace(".", "__") in self.constants:
            return
        import_map = {item.alias: item for item in self.imports}
        if head in import_map:
            imported = import_map[head].system
            if imported is None:
                raise ValueError(f"Import '{head}' is not resolved")
            allowed = set(imported.input_variables.keys()) | set(
                imported.output_variables.keys()
            )
            if tail not in allowed:
                raise ValueError(
                    f"Alias reference '{reference}' must target an imported module input or output"
                )
            return

        raise ValueError(
            f"Alias reference '{reference}' must target an imported module input or output"
        )

    def validate_references(self):
        """Validate all references used by aliases, rules, and connections."""
        for alias_expr in self.aliases.values():
            for reference in self._iter_references(alias_expr):
                self._validate_alias_reference(reference)
        for rule in self.rules:
            for reference in self._iter_references(rule.guard):
                self._validate_reference(reference)
            for reference in self._iter_references(rule.producer):
                self._validate_reference(reference)
        for item in self.imports:
            imported = item.system
            if imported is None:
                continue
            imported_inputs = set(imported.input_variables.keys())
            for port_name, ref in item.connections.items():
                if port_name not in imported_inputs:
                    raise ValueError(
                        f"Import connection '{port_name}' is not an input on '{item.alias}'"
                    )
                self._validate_reference(ref)

    @staticmethod
    def from_yaml(
        file_path: str,
        import_paths: list[str] | None = None,
        _loading_stack: list[Path] | None = None,
        _system_cache: dict[Path, "NncSystem"] | None = None,
        _raw_data_cache: dict[Path, dict] | None = None,
    ):
        """Load a TENNCell system from YAML using the shared loader pipeline.

        Args:
            file_path: Path to the YAML file to load.
            import_paths: Optional search paths for imported TENNCell files.
            _loading_stack: Internal recursion guard for import cycle detection.
            _system_cache: Internal cache of already loaded TENNCell systems.
            _raw_data_cache: Internal cache of parsed YAML dictionaries.
        """
        return load_system_from_yaml(
            NncSystem,
            file_path,
            import_paths=import_paths,
            _loading_stack=_loading_stack,
            _system_cache=_system_cache,
            _raw_data_cache=_raw_data_cache,
        )
