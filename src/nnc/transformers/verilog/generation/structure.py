"""Verilog structural module emission helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....model.system import NncSystem
from ..hardware_config import ExternalInstance, PortConfig

if TYPE_CHECKING:
    from .context import VerilogEmissionContext


class VerilogStructuralEmitter:
    """Emit Verilog ports, wires, submodules, externals, and outputs."""

    def _port_map_for(self, system: NncSystem) -> dict[str, PortConfig]:
        """Return the declared or inferred Verilog ports for one TENNCell module."""
        config = self._config_for(system)
        return {port.name: port for port in (config.ports or self._infer_ports(system))}

    def _infer_ports(self, system: NncSystem) -> list[PortConfig]:
        """Infer a full Verilog boundary from the TENNCell input/output sets."""
        config = self._config_for(system)
        enc = config.real_encoding
        if enc is None:
            raise ValueError("Verilog export requires a verilog.real_encoding section")

        ports: list[PortConfig] = []
        seen: set[str] = set()

        for name in system.input_variables.keys():
            ports.append(PortConfig(name, "input", "fixed", enc.width, enc.signed))
            seen.add(name)

        for name in system.output_variables.keys():
            if name in seen:
                raise ValueError(
                    f"Verilog port '{name}' cannot be both an input and an output"
                )
            ports.append(PortConfig(name, "output", "fixed", enc.width, enc.signed))
            seen.add(name)

        return ports

    def _build_binding_maps(
        self, system: NncSystem
    ) -> tuple[
        dict[str, PortConfig],
        dict[str, tuple[ExternalInstance, PortConfig]],
        dict[str, tuple[ExternalInstance, PortConfig]],
        dict[str, tuple[str, PortConfig]],
    ]:
        """Build the top-level and external variable bindings for a system."""
        config = self._config_for(system)
        top_ports = self._port_map_for(system)
        external_input_bindings: dict[str, tuple[ExternalInstance, PortConfig]] = {}
        external_output_bindings: dict[str, tuple[ExternalInstance, PortConfig]] = {}
        import_output_bindings: dict[str, tuple[str, PortConfig]] = {}
        output_names = set(system.output_variables.keys())

        for item in config.externals:
            if item.definition is None:
                raise ValueError(
                    f"External '{item.alias}' is not resolved to a reusable schema"
                )
            for port in item.definition.ports:
                target_ref = item.connections.get(port.name)
                if target_ref is None:
                    continue
                if "." in target_ref or target_ref == "0":
                    continue
                if port.dir == "output":
                    if target_ref not in system.variables:
                        continue
                    if target_ref in external_output_bindings:
                        raise ValueError(
                            f"Verilog input variable '{target_ref}' is bound more than once by external outputs"
                        )
                    external_output_bindings[target_ref] = (item, port)
                else:
                    if target_ref not in output_names:
                        continue
                    if target_ref in external_input_bindings:
                        raise ValueError(
                            f"Verilog output variable '{target_ref}' is bound more than once by external inputs"
                        )
                    external_input_bindings[target_ref] = (item, port)

        for item in system.imports:
            imported = item.system
            imported_ports = self._port_map_for(imported)
            for output_name in imported.output_variables.keys():
                if output_name not in system.variables:
                    continue
                if output_name in import_output_bindings:
                    raise ValueError(
                        f"Verilog input variable '{output_name}' is bound more than once by imported outputs"
                    )
                imported_port = imported_ports.get(output_name)
                if imported_port is None:
                    continue
                import_output_bindings[output_name] = (item.alias, imported_port)

        return (
            top_ports,
            external_input_bindings,
            external_output_bindings,
            import_output_bindings,
        )

    def _validate_port_bindings(self, system: NncSystem, ctx: VerilogEmissionContext):
        """Validate that all TENNCell IO variables are bound exactly once."""
        if not ctx.config.ports:
            return

        input_names = set(system.input_variables.keys())
        output_names = set(system.output_variables.keys())
        for name in input_names:
            if name not in ctx.top_ports and name not in ctx.external_output_bindings:
                raise ValueError(
                    f"Input variable '{name}' must be described in verilog.ports or verilog.externals"
                )
            if name in ctx.top_ports and name in ctx.external_output_bindings:
                raise ValueError(
                    f"Input variable '{name}' cannot be described in both verilog.ports and verilog.externals"
                )
            if name in ctx.top_ports and ctx.top_ports[name].dir != "input":
                raise ValueError(
                    f"Input variable '{name}' must be bound to an input port"
                )

        for name in output_names:
            if name not in ctx.top_ports and name not in ctx.external_input_bindings:
                raise ValueError(
                    f"Output variable '{name}' must be described in verilog.ports or verilog.externals"
                )
            if name in ctx.top_ports and name in ctx.external_input_bindings:
                raise ValueError(
                    f"Output variable '{name}' cannot be described in both verilog.ports and verilog.externals"
                )
            if name in ctx.top_ports and ctx.top_ports[name].dir != "output":
                raise ValueError(
                    f"Output variable '{name}' must be bound to an output port"
                )
        for name in ctx.external_output_bindings:
            if name not in system.variables:
                raise ValueError(
                    f"External output binding '{name}' must target a TENNCell variable"
                )
        for name in ctx.import_output_bindings:
            if name not in system.variables:
                raise ValueError(
                    f"Imported output binding '{name}' must target a TENNCell variable"
                )
        for name in ctx.external_input_bindings:
            if name not in system.variables:
                raise ValueError(
                    f"External input binding '{name}' must target a TENNCell variable"
                )

        for name in ctx.top_ports:
            if name not in input_names and name not in output_names:
                raise ValueError(
                    f"Verilog port '{name}' does not match any TENNCell input or output variable"
                )

    def _collect_reference_inputs(self, system: NncSystem) -> dict[str, str]:
        """Collect the referenced signals that need Verilog wiring."""
        refs: dict[str, str] = {}
        for rule in system.rules:
            for reference in system._iter_references(rule.guard):
                refs[reference] = self._reference_signal_name(reference)
            for reference in system._iter_references(rule.producer):
                refs[reference] = self._reference_signal_name(reference)
        for alias_expr in system.aliases.values():
            for reference in system._iter_references(alias_expr):
                refs[reference] = self._reference_signal_name(reference)
        return refs

    def _collect_ports(self, system: NncSystem) -> list[PortConfig]:
        """Collect the final Verilog port list for a system."""
        config = self._config_for(system)
        ports = [
            PortConfig(config.clock.name, "input", "logic", 1, False),
            PortConfig(config.reset.name, "input", "logic", 1, False),
        ]
        existing = {ports[0].name, ports[1].name}

        source_ports = config.ports or self._infer_ports(system)
        for port in source_ports:
            if port.name not in existing:
                ports.append(port)
                existing.add(port.name)

        return ports

    def _port_decl(self, port: PortConfig) -> str:
        """Render one Verilog port declaration."""
        signed = " signed" if port.signed and port.width > 1 else ""
        width = "" if port.width == 1 else f" [{port.width - 1}:0]"
        return f"{port.dir} logic{signed}{width} {port.verilog_name}"

    def _emit_import_wires(self, ctx: VerilogEmissionContext | None = None):
        """Emit wires used to connect imported TENNCell modules."""
        ctx = ctx or self._emission_context
        assert ctx is not None
        for item in ctx.system.imports:
            imported = item.system
            port_map = self._port_map_for(imported)
            for output_name in imported.output_variables.keys():
                wire_name = f"{item.alias}__{output_name}"
                imported_port = port_map.get(output_name)
                if imported_port is None:
                    continue
                signed = " signed" if imported_port.signed and imported_port.width > 1 else ""
                width = "" if imported_port.width == 1 else f" [{imported_port.width - 1}:0]"
                self.add_line(f"logic{signed}{width} {wire_name};")
        for target_ref, (_, port) in ctx.import_output_bindings.items():
            signed = " signed" if port.signed and port.width > 1 else ""
            width = "" if port.width == 1 else f" [{port.width - 1}:0]"
            self.add_line(f"logic{signed}{width} {target_ref};")
        if ctx.system.imports or ctx.import_output_bindings:
            self.add_line()

    def _emit_import_output_bindings(
        self, ctx: VerilogEmissionContext | None = None
    ) -> None:
        """Emit assignments that bind imported outputs back into the parent."""
        ctx = ctx or self._emission_context
        assert ctx is not None
        emitted = False
        for item in ctx.system.imports:
            imported = item.system
            imported_ports = self._port_map_for(imported)
            for output_name in imported.output_variables.keys():
                if output_name not in ctx.import_output_bindings:
                    continue
                imported_port = imported_ports.get(output_name)
                if imported_port is None:
                    continue
                target_signal = output_name
                source_signal = f"{item.alias}__{output_name}"
                _, target_port = ctx.import_output_bindings[output_name]
                converted = self._external_output_to_target(
                    source_signal,
                    imported_port.kind,
                    imported_port.width,
                    imported_port.signed,
                    0
                    if imported_port.kind != "fixed"
                    else self._config_for(imported).real_encoding.frac_bits,
                    target_port.kind,
                    target_port.width,
                    target_port.signed,
                    0 if target_port.kind != "fixed" else ctx.config.real_encoding.frac_bits,
                )
                self.add_line(f"assign {target_signal} = {converted};")
                emitted = True
        if emitted:
            self.add_line()

    def _emit_external_wires(self, ctx: VerilogEmissionContext | None = None):
        """Emit wires used to connect external Verilog modules."""
        ctx = ctx or self._emission_context
        assert ctx is not None
        for item in ctx.config.externals:
            if item.definition is None:
                raise ValueError(
                    f"External '{item.alias}' is not resolved to a reusable schema"
                )
            for port in item.definition.ports:
                if port.dir == "output":
                    signed = " signed" if port.signed and port.width > 1 else ""
                    width = "" if port.width == 1 else f" [{port.width - 1}:0]"
                    self.add_line(f"logic{signed}{width} {item.alias}__{port.name};")
        for target_ref, (_, port) in ctx.external_output_bindings.items():
            if target_ref in ctx.top_ports:
                continue
            signed = " signed" if port.signed and port.width > 1 else ""
            width = "" if port.width == 1 else f" [{port.width - 1}:0]"
            self.add_line(f"logic{signed}{width} {target_ref};")
        if ctx.config.externals:
            self.add_line()

    def _emit_external_output_bindings(self, ctx: VerilogEmissionContext | None = None):
        """Emit assignments that bind external outputs back into the design."""
        ctx = ctx or self._emission_context
        assert ctx is not None
        config = ctx.config
        emitted = False
        output_names = set(ctx.system.output_variables.keys())
        for item in config.externals:
            if item.definition is None:
                raise ValueError(
                    f"External '{item.alias}' is not resolved to a reusable schema"
                )
            for port in item.definition.ports:
                if port.dir != "output":
                    continue
                target_ref = item.connections.get(port.name)
                if not target_ref:
                    continue
                if "." not in target_ref and target_ref in output_names:
                    continue
                source_signal = f"{item.alias}__{port.name}"
                assert config.real_encoding is not None
                source_frac_bits = (
                    config.real_encoding.frac_bits if port.kind == "fixed" else 0
                )
                target_encoding = None
                if target_ref in ctx.external_output_bindings:
                    target_signal = target_ref
                    target_encoding = self._reference_encoding(target_ref, ctx)
                elif "." not in target_ref and target_ref in ctx.system.variables:
                    target_signal = self._state_name(target_ref)
                    target_kind = "fixed"
                    target_width = config.real_encoding.width
                    target_signed = config.real_encoding.signed
                    target_frac_bits = config.real_encoding.frac_bits
                else:
                    target_signal = self._reference_signal(target_ref)
                    target_encoding = self._reference_encoding(target_ref, ctx)
                if target_encoding is not None:
                    target_kind = target_encoding.kind
                    target_width = target_encoding.width
                    target_signed = target_encoding.signed
                    target_frac_bits = (
                        target_encoding.frac_bits
                        if target_encoding.kind == "fixed"
                        else 0
                    )
                converted = self._external_output_to_target(
                    source_signal,
                    port.kind,
                    port.width,
                    port.signed,
                    source_frac_bits,
                    target_kind,
                    target_width,
                    target_signed,
                    target_frac_bits,
                )
                self.add_line(f"assign {target_signal} = {converted};")
                emitted = True
        if emitted:
            self.add_line()

    def _emit_submodules(self, ctx: VerilogEmissionContext | None = None):
        """Emit imported TENNCell modules and external module instances."""
        ctx = ctx or self._emission_context
        assert ctx is not None
        config = ctx.config
        for item in ctx.system.imports:
            imported = item.system
            imported_config = self._config_for(imported)
            imported_ports = self._port_map_for(imported)
            self.add_line(f"{imported.module_config.name} {item.alias} (")
            connections = []
            connections.append(f".{imported_config.clock.name}({config.clock.name})")
            connections.append(f".{imported_config.reset.name}({config.reset.name})")
            for input_name in imported.input_variables.keys():
                ref = item.connections.get(input_name, "0")
                imported_port = imported_ports.get(input_name)
                if imported_port is None:
                    continue
                connections.append(
                    f".{input_name}({self._resolve_connection(ref, imported_port.kind, imported_port.width, imported_port.signed, 0 if imported_port.kind != 'fixed' else imported_config.real_encoding.frac_bits, ctx)})"
                )
            for output_name in imported.output_variables.keys():
                connections.append(f".{output_name}({item.alias}__{output_name})")
            for index, conn in enumerate(connections):
                suffix = "," if index < len(connections) - 1 else ""
                self.add_line(f"{conn}{suffix}", 1)
            self.add_line(");")
            self.add_line()

        for item in config.externals:
            if item.definition is None:
                raise ValueError(
                    f"External '{item.alias}' is not resolved to a reusable schema"
                )
            header = item.definition
            param_lines = []
            merged_params = dict(header.parameters)
            merged_params.update(item.parameters)
            if merged_params:
                params = ", ".join(
                    f".{key}({value})" for key, value in merged_params.items()
                )
                param_lines.append(f"#({params})")
            prefix = (
                f"{header.module} {param_lines[0]} {item.alias}"
                if param_lines
                else f"{header.module} {item.alias}"
            )
            self.add_line(f"{prefix} (")
            connections = []
            for port in header.ports:
                if port.dir == "output":
                    target = f"{item.alias}__{port.name}"
                else:
                    target = self._resolve_connection(
                        item.connections.get(port.name, "0"),
                        port.kind,
                        port.width,
                        port.signed,
                        0 if port.kind != "fixed" else config.real_encoding.frac_bits,
                        ctx,
                    )
                connections.append(f".{port.name}({target})")
            for index, conn in enumerate(connections):
                suffix = "," if index < len(connections) - 1 else ""
                self.add_line(f"{conn}{suffix}", 1)
            self.add_line(");")
            self.add_line()

    def _emit_outputs(self, ctx: VerilogEmissionContext | None = None):
        """Emit the top-level output assignments for the generated module."""
        ctx = ctx or self._emission_context
        assert ctx is not None
        config = ctx.config
        for output_name in ctx.system.output_variables.keys():
            top_port = self._top_port_config(output_name, ctx)
            if top_port is None:
                continue
            external_assignment = None
            if output_name in ctx.import_output_bindings:
                alias, port = ctx.import_output_bindings[output_name]
                source_signal = f"{alias}__{port.name}"
                imported_config = None
                for item in ctx.system.imports:
                    if item.alias == alias:
                        imported_config = self._config_for(item.system)
                        break
                assert imported_config is not None
                assert imported_config.real_encoding is not None
                external_assignment = self._external_output_to_target(
                    source_signal,
                    port.kind,
                    port.width,
                    port.signed,
                    0 if port.kind != "fixed" else imported_config.real_encoding.frac_bits,
                    top_port.kind,
                    top_port.width,
                    top_port.signed,
                    0 if top_port.kind != "fixed" else config.real_encoding.frac_bits,
                    ctx,
                )
            for item in config.externals:
                if item.definition is None:
                    raise ValueError(
                        f"External '{item.alias}' is not resolved to a reusable schema"
                    )
                for port in item.definition.ports:
                    if port.dir != "output":
                        continue
                    if item.connections.get(port.name) != output_name:
                        continue
                    source_signal = f"{item.alias}__{port.name}"
                    assert config.real_encoding is not None
                    external_assignment = self._external_output_to_target(
                        source_signal,
                        port.kind,
                        port.width,
                        port.signed,
                        config.real_encoding.frac_bits
                        if port.kind == "fixed"
                        else 0,
                        top_port.kind,
                        top_port.width,
                        top_port.signed,
                        0 if top_port.kind != "fixed" else config.real_encoding.frac_bits,
                        ctx,
                    )
                    break
                if external_assignment is not None:
                    break
            if external_assignment is None:
                self.add_line(
                    f"assign {top_port.verilog_name} = {self._convert_local_fixed_to_target(output_name, top_port.kind, top_port.width, top_port.signed, ctx)};"
                )
            else:
                self.add_line(f"assign {top_port.verilog_name} = {external_assignment};")
        if ctx.system.output_variables:
            self.add_line()
