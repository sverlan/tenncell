"""Verilog state and next-state logic emission helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .context import VerilogEmissionContext
    from .host import VerilogEmitterHost as _Host
else:
    _Host = object


class VerilogStateEmitter(_Host):
    """Emit TENNCell state declarations and sequential/next-state logic."""

    def _emit_state(self, ctx: VerilogEmissionContext | None = None):
        """Emit state storage declarations for the local variables."""
        ctx = ctx or self._emission_context
        assert ctx is not None
        for variable_name in ctx.local_variables:
            encoding = self._variable_state_encoding(variable_name, ctx)
            state_name = self._state_name(variable_name)
            self.add_line(
                f"{self._type_decl(encoding.kind, encoding.width, encoding.signed)} {state_name};"
            )
            self.add_line(
                f"{self._type_decl(encoding.kind, encoding.width, encoding.signed)} {state_name}_next;"
            )
            self.add_line(
                f"{self._type_decl(encoding.kind, encoding.width, encoding.signed)} {state_name}_prod;"
            )
            if not ctx.system.module_config.zero_reset_mode:
                self.add_line(f"logic {state_name}_used;")
        self.add_line()

    def _emit_next_state_logic(self, ctx: VerilogEmissionContext | None = None):
        """Emit the combinational and sequential next-state logic."""
        ctx = ctx or self._emission_context
        assert ctx is not None
        config = ctx.config
        self.add_line("always_comb begin")
        for variable_name in ctx.local_variables:
            state_name = self._state_name(variable_name)
            self.add_line(f"{state_name}_prod = '0;", 1)
            if not ctx.system.module_config.zero_reset_mode:
                self.add_line(f"{state_name}_used = 1'b0;", 1)
        self.add_line()
        for rule in ctx.system.rules:
            guard = self.visit(rule.guard, ctx)
            producer = self._emit_in_encoding(
                rule.producer,
                self._variable_state_encoding(rule.consumer.name, ctx),
                ctx,
            )
            self.add_line(f"// {rule}", 1)
            emit_if = (
                guard.__class__.__name__ != "BooleanConstantExpression"
                or getattr(rule.guard, "value", None) is not True
            )
            if emit_if:
                self.add_line(f"if ({guard}) begin", 1)
            consumer_state = self._state_name(rule.consumer.name)
            body_indent = 2 if emit_if else 1
            self.add_line(
                f"{consumer_state}_prod = {consumer_state}_prod + {producer};",
                body_indent,
            )
            if not ctx.system.module_config.zero_reset_mode:
                for used_name in sorted(rule.vars.keys()):
                    if used_name not in ctx.local_variables:
                        continue
                    used_state = self._state_name(used_name)
                    self.add_line(f"{used_state}_used = 1'b1;", body_indent)
            if emit_if:
                self.add_line("end", 1)
        self.add_line()
        for variable_name in ctx.local_variables:
            state_name = self._state_name(variable_name)
            if ctx.system.module_config.zero_reset_mode:
                if variable_name in ctx.system.input_variables:
                    self.add_line(
                        f"{state_name}_next = {self._variable_signal_name(variable_name, ctx)};",
                        1,
                    )
                else:
                    self.add_line(f"{state_name}_next = '0;", 1)
            else:
                if variable_name in ctx.system.input_variables:
                    self.add_line(
                        f"{state_name}_next = {self._variable_signal_name(variable_name, ctx)};",
                        1,
                    )
                else:
                    self.add_line(f"{state_name}_next = {state_name};", 1)
                self.add_line(f"if ({state_name}_used) begin", 1)
                self.add_line(f"{state_name}_next = '0;", 2)
                self.add_line("end", 1)
            self.add_line(
                f"{state_name}_next = {state_name}_next + {state_name}_prod;", 1
            )
        self.add_line("end")
        self.add_line()

        reset_edge = "posedge" if config.reset.active_high else "negedge"
        self.add_line(
            f"always_ff @(posedge {config.clock.name} or {reset_edge} {config.reset.name}) begin"
        )
        reset_condition = (
            config.reset.name if config.reset.active_high else f"!{config.reset.name}"
        )
        self.add_line(f"if ({reset_condition}) begin", 1)
        for variable_name in ctx.local_variables:
            target = self._variable_state_encoding(variable_name, ctx)
            initial_value = self._emit_constant_in_encoding(
                ctx.system.variables[variable_name].value.value,
                target,
                ctx,
            )
            self.add_line(
                f"// reset {variable_name} = {ctx.system.variables[variable_name].value.value}",
                2,
            )
            self.add_line(f"{self._state_name(variable_name)} <= {initial_value};", 2)
        self.add_line("end else begin", 1)
        for variable_name in ctx.local_variables:
            self.add_line(
                f"{self._state_name(variable_name)} <= {self._state_name(variable_name)}_next;",
                2,
            )
        self.add_line("end", 1)
        self.add_line("end")
        self.add_line()

    def _state_name(self, variable_name: str) -> str:
        """Return the generated state signal name for a variable."""
        return f"state_{variable_name}"
