"""Verilog transformer for converting TENNCell AST to a synthesizable subset."""

from __future__ import annotations

from pathlib import Path

from .base_transformer import BaseTransformer
from .verilog.generation.conversions import VerilogConversionEmitter
from .verilog.generation.expressions import VerilogExpressionEmitter
from .verilog.generation.references import VerilogReferenceResolver
from .verilog.generation.state import VerilogStateEmitter
from .verilog.generation.structure import VerilogStructuralEmitter
from .verilog.generation.context import VerilogEmissionContext
from .verilog.generation.keywords import SYSTEMVERILOG_KEYWORDS
from .verilog.generation.observation import VerilogObservation, build_observation
from .verilog.hardware_config import (
    VerilogFixedPointTypeInfo,
    VerilogHardwareConfig,
    VerilogLogicTypeInfo,
    VerilogTypeInfo,
)
from ..inputs.yaml.errors import YamlLocatedError
from ..model.system import NncSystem


class VerilogTransformer(
    VerilogStructuralEmitter,
    VerilogStateEmitter,
    VerilogReferenceResolver,
    VerilogConversionEmitter,
    VerilogExpressionEmitter,
    BaseTransformer,
):
    """Transform TENNCell systems into parameterized Verilog modules."""

    def __init__(
        self, verilog_configs: dict[Path, VerilogHardwareConfig] | None = None
    ):
        super().__init__()
        self.verilog_configs = verilog_configs or {}
        self._emission_context: VerilogEmissionContext | None = None

    def set_verilog_configs(self, configs: dict[Path, VerilogHardwareConfig]):
        """Replace the Verilog hardware config mapping used during emission."""
        self.verilog_configs = configs

    def _config_for(self, system: NncSystem) -> VerilogHardwareConfig:
        """Look up the Verilog hardware config for a loaded TENNCell system."""
        if system.source_path is None:
            raise ValueError("Verilog export requires systems loaded from YAML files")
        try:
            return self.verilog_configs[system.source_path]
        except KeyError as e:
            raise ValueError(
                f"Missing Verilog configuration for '{system.source_path}'"
            ) from e

    def _interface_variable_names(
        self,
        system: NncSystem,
    ) -> set[str]:
        """Return TENNCell variable names that are true top-level interface members."""
        return set(system.input_variables.keys()) | set(system.output_variables.keys())

    def _resolved_internal_types(
        self,
        system: NncSystem,
        config: VerilogHardwareConfig,
        interface_names: set[str],
    ) -> dict[str, VerilogTypeInfo]:
        """Validate and return internal Verilog type hints for a module."""
        if system.source_path is None:
            raise ValueError("Verilog export requires systems loaded from YAML files")
        resolved: dict[str, VerilogTypeInfo] = {}
        for name, type_info in config.types.items():
            line = config.type_lines.get(name)
            if name not in system.variables:
                raise YamlLocatedError(
                    f"verilog.types entry '{name}' does not match any TENNCell variable",
                    system.source_path,
                    line,
                )
            if name in interface_names:
                raise YamlLocatedError(
                    f"verilog.types entry '{name}' must not describe an interface variable",
                    system.source_path,
                    line,
                )
            resolved[name] = type_info
        return resolved

    def _type_info_from_port(self, port, real_encoding) -> VerilogTypeInfo:
        """Convert one port declaration into a backend Verilog type hint."""
        if port.kind == "fixed":
            assert real_encoding is not None
            return VerilogFixedPointTypeInfo(
                kind="fixed_point",
                width=port.width,
                frac_bits=real_encoding.frac_bits,
                signed=port.signed,
            )
        return VerilogLogicTypeInfo(
            kind="logic",
            width=port.width,
            signed=port.signed,
        )

    def _interface_variable_types(
        self,
        system: NncSystem,
        config: VerilogHardwareConfig,
    ) -> dict[str, VerilogTypeInfo]:
        """Infer effective types for locals that participate in interfaces."""
        resolved: dict[str, VerilogTypeInfo] = {}

        def add(name: str, type_info: VerilogTypeInfo) -> None:
            if name in system.input_variables or name in system.output_variables:
                return
            if name not in system.variables:
                return
            resolved[name] = type_info

        for item in system.imports:
            imported_config = self._config_for(item.system)
            imported_ports = self._port_map_for(item.system)
            for input_name in item.system.input_variables.keys():
                ref = item.connections.get(input_name, "0")
                if "." in ref or ref == "0":
                    continue
                imported_port = imported_ports.get(input_name)
                if imported_port is None:
                    continue
                add(
                    ref,
                    self._type_info_from_port(
                        imported_port, imported_config.real_encoding
                    ),
                )
            for output_name in item.system.output_variables.keys():
                if output_name not in system.variables:
                    continue
                imported_port = imported_ports.get(output_name)
                if imported_port is None:
                    continue
                add(
                    output_name,
                    self._type_info_from_port(
                        imported_port,
                        imported_config.real_encoding,
                    ),
                )

        for item in config.externals:
            if item.definition is None:
                continue
            for port in item.definition.ports:
                ref = item.connections.get(port.name)
                if ref is None or "." in ref or ref == "0":
                    continue
                add(ref, self._type_info_from_port(port, config.real_encoding))

        return resolved

    def get_file_extension(self) -> str:
        return ".sv"

    def observe(self, system: NncSystem) -> VerilogObservation:
        """Return the TENNCell values observable in the module ``transform`` emits.

        The signal names and encodings come from the same emission context and
        helpers as the generated RTL, so they always match it.

        Args:
            system: TENNCell system loaded from YAML, with its Verilog config.

        Returns:
            The module's clock/reset and one ``ObservedSignal`` per root variable,
            imported output (``alias.port``) and imported input.

        Raises:
            ValueError: If the system cannot be emitted as Verilog.
            YamlLocatedError: If a Verilog type hint is invalid.
        """
        previous = self._emission_context
        try:
            ctx = self._build_emission_context(system)
            return build_observation(self, ctx)
        finally:
            self._emission_context = previous

    def _build_emission_context(self, system: NncSystem) -> VerilogEmissionContext:
        """Validate a system and build the emission context shared by the RTL
        emission and ``observe``."""
        self._validate_supported_system(system)
        config = self._config_for(system)
        if config.real_encoding is None:
            raise ValueError("Verilog export requires a verilog.real_encoding section")
        (
            top_ports,
            external_input_bindings,
            external_output_bindings,
            import_output_bindings,
        ) = self._build_binding_maps(system)
        resolved_var_types = self._resolved_internal_types(
            system,
            config,
            self._interface_variable_names(system),
        )
        resolved_var_types.update(
            self._interface_variable_types(
                system,
                config,
            )
        )
        ctx = VerilogEmissionContext(
            system=system,
            config=config,
            local_variables=sorted(
                set(system.variables.keys())
                - set(system.input_variables.keys())
                - set(external_output_bindings.keys())
                - set(import_output_bindings.keys())
            ),
            top_ports=top_ports,
            external_input_bindings=external_input_bindings,
            external_output_bindings=external_output_bindings,
            import_output_bindings=import_output_bindings,
            resolved_var_types=resolved_var_types,
            reference_inputs=self._collect_reference_inputs(system),
        )
        self._emission_context = ctx
        self._validate_port_bindings(system, ctx)
        self._validate_identifiers(system, ctx)
        return ctx

    def _validate_identifiers(
        self, system: NncSystem, ctx: VerilogEmissionContext
    ) -> None:
        """Reject model names the RTL would emit as SystemVerilog keywords."""
        names: list[tuple[str, str]] = [
            (system.module_config.name, "the module name (set module.name)")
        ]
        for port in self._collect_ports(system):
            names.append(
                (port.verilog_name, "a port name (use rename in verilog.ports)")
            )
        names += [(name, "a constant name") for name in system.constants]
        for item in system.imports:
            # The parent instantiates the child by module name and port names.
            child = item.system
            names.append(
                (
                    child.module_config.name,
                    f"the name of imported module '{item.alias}' (set module.name "
                    f"in {child.source_path})",
                )
            )
            names += [
                (port.verilog_name, f"a port name of imported module '{item.alias}'")
                for port in self._collect_ports(child)
            ]
            names.append((item.alias, "an import alias"))
        names += [(item.alias, "an external alias") for item in ctx.config.externals]
        wires = set(ctx.import_output_bindings) | set(ctx.external_output_bindings)
        names += [
            (name, "a variable name (it is a wire of the RTL)")
            for name in sorted(wires - set(ctx.top_ports))
        ]
        for name, role in names:
            if name in SYSTEMVERILOG_KEYWORDS:
                raise ValueError(
                    f"'{name}' is a SystemVerilog keyword and cannot be {role} "
                    f"in the Verilog generated for '{system.source_path}'"
                )

    def transform(self, system: NncSystem) -> str:
        self.reset()
        ctx = self._build_emission_context(system)
        module_name = system.module_config.name
        config = ctx.config
        enc = config.real_encoding
        assert enc is not None
        ports = self._collect_ports(system)
        port_lines = [self._port_decl(port) for port in ports]

        self.add_line("`default_nettype none")
        self.add_line()
        self.add_line(f"module {module_name} #(")
        self.add_line(f"parameter int DATA_WIDTH = {enc.width},", 1)
        self.add_line(f"parameter int FRAC_BITS = {enc.frac_bits}", 1)
        self.add_line(") (")
        for index, line in enumerate(port_lines):
            suffix = "," if index < len(port_lines) - 1 else ""
            self.add_line(f"{line}{suffix}", 1)
        self.add_line(");")
        self.add_line()

        for const_name, value in system.constants.items():
            self.add_line(
                f"// {const_name} = {value.value} in fixed-point Q{enc.width - enc.frac_bits}.{enc.frac_bits}"
            )
            self.add_line(
                f"localparam {self._fixed_storage_decl(enc.width, enc.signed)} {const_name} = {self._encode_float(value.value, enc.width, enc.frac_bits, enc.signed)};"
            )
        if system.constants:
            self.add_line()
        self.add_line("// __LITERAL_PARAMS__")
        self.add_line()
        self.add_line("// __CONVERSION_HELPERS__")
        self.add_line()

        self._emit_import_wires(ctx)
        self._emit_external_wires(ctx)
        self._emit_state(ctx)
        self._emit_submodules(ctx)
        self._emit_import_output_bindings(ctx)
        self._emit_external_output_bindings(ctx)
        self._emit_next_state_logic(ctx)
        self._emit_outputs(ctx)

        self.add_line("endmodule")
        helper_text = self._emit_conversion_helpers(ctx)
        literal_text = self._emit_literal_params(ctx)
        return (
            self.get_output()
            .replace("// __LITERAL_PARAMS__\n\n", literal_text)
            .replace("// __CONVERSION_HELPERS__\n\n", helper_text)
        )


def rtl_file_name(system: NncSystem, suffix: str = "") -> str:
    """Return the RTL file name of a module: ``<source stem><suffix>.sv``.

    Args:
        system: Module loaded from YAML.
        suffix: Optional suffix added to the stem (``nnc-gen --output-suffix``).

    Returns:
        The file name, as ``nnc-gen -t verilog`` writes it.
    """
    assert system.source_path is not None
    return f"{Path(system.source_path).stem}{suffix}.sv"


def check_distinct_rtl_file_names(closure: list[NncSystem], suffix: str = "") -> None:
    """Reject an import closure in which two modules get the same RTL file name.

    Two modules from different folders with the same source file name (for
    example ``a/controller.yaml`` and ``b/controller.yaml``) would both be
    written to ``controller.sv``, and one module would be lost.
    Names are compared case-insensitively.

    Args:
        closure: Modules of the import closure.
        suffix: Optional suffix added to every stem.

    Raises:
        ValueError: Naming every source file that maps to a duplicate name.
    """
    # Compared case-insensitively: Controller.sv and controller.sv are the same
    # file on Windows and macOS, and generated RTL may move between systems.
    by_key: dict[str, list[tuple[str, str]]] = {}
    for item in closure:
        name = rtl_file_name(item, suffix)
        by_key.setdefault(name.casefold(), []).append((name, str(item.source_path)))
    clashes = [entries for entries in by_key.values() if len(entries) > 1]
    if clashes:
        details = "; ".join(
            " and ".join(f"{name} from {path}" for name, path in entries)
            for entries in clashes
        )
        raise ValueError(
            "two modules of the import closure would be written to the same RTL "
            f"file, so one module would be lost: {details}; rename one of the "
            "source files"
        )
