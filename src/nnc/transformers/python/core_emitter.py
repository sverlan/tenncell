"""Reusable Python TENNCell core code emission helpers."""

from pathlib import Path

from ...inputs.yaml.module_config import connection_number
from ...model.system import NncSystem
from .emission_context import PythonEmissionContext
from .expression_emitter import UnsupportedFunctionError


class PythonCoreEmitter:
    """Emit Python TENNCell system classes, modules, and step methods."""

    def _zero_reset_mode(self, system: NncSystem) -> bool:
        """Return whether the TENNCell system should use zero-reset semantics."""
        module_config = getattr(system, "module_config", None)
        return bool(getattr(module_config, "zero_reset_mode", False))

    def _input_vars(self, system: NncSystem) -> list[str]:
        """Return the ordered list of input variable names for a system."""
        return list(system.input_variables.keys()) if system.input_variables else []

    def _output_vars(self, system: NncSystem) -> list[str]:
        """Return the ordered list of output variable names for a system."""
        return list(system.output_variables.keys()) if system.output_variables else []

    def _emit_variable_initializers(
        self,
        system: NncSystem,
        indent: int,
        track_declarations: bool = False,
        ctx: PythonEmissionContext | None = None,
    ):
        """Emit instance attributes for the system variables."""
        ctx = ctx or self._emission_context
        emitted = False
        for cell in system.cells:
            for var_name, variable in cell.contents.items():
                if track_declarations:
                    assert ctx is not None
                    if var_name in ctx.variable_declarations:
                        continue
                    ctx.variable_declarations.add(var_name)
                self.add_line(
                    f"self.{var_name} = {self.visit_value(variable.value)}", indent
                )
                emitted = True
        return emitted

    def _emit_step_method(
        self,
        system: NncSystem,
        var_names: list[str],
        input_vars: list[str],
        output_vars: list[str],
        *,
        indent: int,
        signature: str,
        coerce_inputs: bool,
        input_value_wrapper: str,
        include_docstring: bool,
        ctx: PythonEmissionContext | None = None,
    ):
        """Emit the generated `step()` method for a TENNCell module."""
        ctx = ctx or self._emission_context
        self.add_line(f"def step(self{signature}):", indent)
        body_indent = indent + 1
        if include_docstring:
            self._emit_step_docstring(input_vars, output_vars, body_indent)
        if coerce_inputs:
            self.add_line(f"required_inputs = {input_vars}", body_indent)
            self.add_line(
                "inputs = self._coerce_inputs(inputs, required_inputs)", body_indent
            )
        elif input_vars:
            self._emit_required_input_validation(input_vars, body_indent)
        self._emit_input_updates(input_vars, body_indent, input_value_wrapper)
        self._emit_import_steps(system, body_indent)
        self.add_line("# TENNCell step using _new variables approach", body_indent)
        self.add_line()
        self._emit_step_body(
            system, var_names, input_vars, output_vars, body_indent, ctx=ctx
        )

    def _emit_step_docstring(
        self, input_vars: list[str], output_vars: list[str], indent: int
    ):
        """Emit the docstring for the generated `step()` method."""
        self.add_line('"""Execute one step of the TENNCell system.', indent)
        self.add_line("", indent)
        if input_vars:
            self.add_line("Args:", indent)
            self.add_line(
                "inputs: Dictionary with input variable values (required)", indent + 1
            )
            self.add_line("", indent)
        self.add_line("Returns:", indent)
        if output_vars:
            self.add_line("Dictionary with output variable values", indent + 1)
        else:
            self.add_line("Dictionary with all variable values", indent + 1)
        self.add_line('"""', indent)

    def _emit_required_input_validation(self, input_vars: list[str], indent: int):
        """Emit runtime checks for required step inputs."""
        self.add_line("# Validate that all input variables are provided", indent)
        self.add_line(f"required_inputs = {input_vars}", indent)
        self.add_line("for var_name in required_inputs:", indent)
        self.add_line("if var_name not in inputs:", indent + 1)
        self.add_line(
            "raise ValueError(f'Input variable {var_name} is required but not provided')",
            indent + 2,
        )
        self.add_line()

    def _emit_input_updates(
        self, input_vars: list[str], indent: int, value_wrapper: str
    ):
        """Emit assignments that copy step inputs into instance attributes."""
        if not input_vars:
            return
        self.add_line("# Update input variables", indent)
        for var_name in input_vars:
            self.add_line(
                f"self.{var_name} = {value_wrapper.format(var_name=var_name)}", indent
            )
        self.add_line()

    def _emit_import_steps(self, system: NncSystem, indent: int):
        """Emit recursive step calls for imported TENNCell modules.

        All imports are given values of the configuration before the step
        (including other imports' outputs) before any of them steps, as in
        ``NncSystem.step``.
        """
        imports = getattr(system, "__dict__", {}).get("imports", [])
        if not imports:
            return
        self.add_line(
            "# Every import reads the configuration before this step.", indent
        )
        for item in imports:
            assert item.system is not None
            child_inputs = []
            for input_name in item.system.input_variables.keys():
                ref = item.connections.get(input_name)
                if ref is None:
                    child_inputs.append(f"'{input_name}': 0.0")
                elif connection_number(ref) is not None:
                    child_inputs.append(f"'{input_name}': {connection_number(ref)!r}")
                elif "." in ref:
                    child_inputs.append(
                        f"'{input_name}': float({self._reference_code(ref)})"
                    )
                elif ref in system.constants:
                    child_inputs.append(
                        f"'{input_name}': {system.constants[ref].value}"
                    )
                else:
                    child_inputs.append(f"'{input_name}': float(self.{ref})")
            self.add_line(
                f"_inputs_{item.alias} = {{{', '.join(child_inputs)}}}", indent
            )
        for item in imports:
            self.add_line(
                f"self._import_{item.alias}.step(_inputs_{item.alias})", indent
            )
        self.add_line()

    def _emit_step_body(
        self,
        system: NncSystem,
        var_names: list[str],
        input_vars: list[str],
        output_vars: list[str],
        indent: int,
        ctx: PythonEmissionContext | None = None,
    ):
        """Emit the body of the generated `step()` method."""
        ctx = ctx or self._emission_context
        zero_reset_mode = self._zero_reset_mode(system)
        # Qualified FSM states (``fsm.STATE``) resolve against this system's constants.
        self._current_system = system
        self.add_line("# Step 1: Evaluate rules on the current state", indent)
        if not zero_reset_mode:
            self.add_line("used_vars = set()", indent)
        emitted_rules: list[tuple[str, bool]] = []
        for i, rule in enumerate(system.rules):
            self.add_line(f"# Rule {i + 1}", indent)
            try:
                guard_code = self.visit(rule.guard)
                producer_code = self.visit(rule.producer)
            except UnsupportedFunctionError as error:
                raise UnsupportedFunctionError(f"{error} (rule: {rule})") from error
            consumer_name = (
                rule.consumer.name
                if hasattr(rule.consumer, "name")
                else str(rule.consumer)
            )
            producer_vars = sorted(self._get_producer_variables(rule.producer))
            body_indent = indent
            unconditional = guard_code in {"True", "1"}
            emitted_rules.append((consumer_name, unconditional))
            if not unconditional:
                self.add_line(f"_g{i} = {guard_code}", indent)
                self.add_line(f"if _g{i}:", indent)
                body_indent += 1
            self.add_line(f"_p{i} = {producer_code}", body_indent)
            if not zero_reset_mode:
                for var_name in producer_vars:
                    self.add_line(f"used_vars.add('{var_name}')", body_indent)
            self.add_line()

        step_mode_label = "zero" if zero_reset_mode else "consumption"
        self.add_line(
            f"# Step 2: Initialize _new versions of all variables from {step_mode_label} state",
            indent,
        )
        for var_name in var_names:
            if zero_reset_mode:
                initial_value = f"self.{var_name}" if var_name in input_vars else "0.0"
            else:
                initial_value = f"0.0 if '{var_name}' in used_vars else self.{var_name}"
            self.add_line(f"{var_name}_new = {initial_value}", indent)
        self.add_line()

        self.add_line("# Step 3: Accumulate stored productions in rule order", indent)
        for i, (consumer_name, unconditional) in enumerate(emitted_rules):
            if unconditional:
                self.add_line(f"{consumer_name}_new += _p{i}", indent)
            else:
                self.add_line(f"if _g{i}:", indent)
                self.add_line(f"{consumer_name}_new += _p{i}", indent + 1)
        self.add_line()

        self.add_line("# Step 4: Update all variables to their final values", indent)
        for var_name in var_names:
            self.add_line(f"self.{var_name} = {var_name}_new", indent)
        self.add_line()
        self._emit_return_outputs(output_vars, indent)

    def _emit_return_outputs(self, output_vars: list[str], indent: int):
        """Emit the return statement for the generated `step()` method."""
        if output_vars:
            self.add_line("# Return output variables", indent)
            self.add_line("return {", indent)
            for var_name in output_vars:
                self.add_line(f"'{var_name}': self.{var_name},", indent + 1)
            self.add_line("}", indent)
        else:
            self.add_line("# No output variables defined, return all variables", indent)
            self.add_line("return self.get_variables()", indent)

    def _emit_get_variables(self, var_names: list[str], indent: int):
        """Emit a helper that returns all generated variables as a mapping."""
        self.add_line("def get_variables(self):", indent)
        self.add_line("return {", indent + 1)
        for var_name in var_names:
            self.add_line(f"'{var_name}': self.{var_name},", indent + 2)
        self.add_line("}", indent + 1)

    def _emit_base_class(self):
        """Emit the small runtime base class shared by generated modules."""
        self.add_line("class _NncModuleBase:")
        self.add_line("def _ref(self, reference):", 1)
        self.add_line("head, _, tail = reference.partition('.')", 2)
        self.add_line("module = getattr(self, f'_import_{head}', None)", 2)
        self.add_line("if module is None:", 2)
        self.add_line("raise ValueError(f'Unknown import reference {reference}')", 3)
        self.add_line("return getattr(module, tail)", 2)
        self.add_line()
        self.add_line("def _coerce_inputs(self, inputs, required_inputs):", 1)
        self.add_line("inputs = inputs or {}", 2)
        self.add_line("for var_name in required_inputs:", 2)
        self.add_line("if var_name not in inputs:", 3)
        self.add_line(
            "raise ValueError(f'Input variable {var_name} is required but not provided')",
            4,
        )
        self.add_line("return inputs", 2)
        self.add_line()

    def _emit_module_class(
        self,
        system: NncSystem,
        ctx: PythonEmissionContext | None = None,
        emitted: set[Path] | None = None,
    ):
        """Emit a generated Python class for one TENNCell system."""
        ctx = ctx or self._emission_context
        assert ctx is not None
        emitted = emitted or ctx.emitted_modules
        assert system.source_path is not None
        if system.source_path in emitted:
            return
        for item in system.imports:
            assert item.system is not None
            self._emit_module_class(item.system, ctx, emitted)

        class_name = self._class_name(system, ctx)
        self.add_line(f"class {class_name}(_NncModuleBase):")
        self.add_line("def __init__(self):", 1)
        emitted_init = self._emit_variable_initializers(system, 2, ctx=ctx)
        for item in system.imports:
            assert item.system is not None
            self.add_line(
                f"self._import_{item.alias} = {self._class_name(item.system, ctx)}()", 2
            )
        if not emitted_init and not system.imports:
            self.add_line("pass", 2)
        self.add_line()

        input_vars = self._input_vars(system)
        output_vars = self._output_vars(system)
        var_names = sorted(system.variables.keys())
        self._emit_step_method(
            system,
            var_names,
            input_vars,
            output_vars,
            indent=1,
            signature=", inputs=None",
            coerce_inputs=True,
            input_value_wrapper="float(inputs['{var_name}'])",
            include_docstring=False,
            ctx=ctx,
        )
        self.add_line()
        self._emit_get_variables(var_names, 1)
        self.add_line()
        emitted.add(system.source_path)
