"""Webots controller transformer for TENNCell systems."""

from __future__ import annotations

from pathlib import Path

from ..model.system import NncSystem
from .base_transformer import BaseTransformer
from .python_transformer import PythonTransformer
from .webots.emission_context import WebotsEmissionContext
from .webots.webots_config import WebotsConfig


class WebotsTransformer(BaseTransformer):
    """Transform TENNCell systems into standalone Webots Python controllers."""

    def __init__(self, webots_configs: dict[Path, WebotsConfig] | None = None) -> None:
        """Create a Webots transformer.

        Args:
            webots_configs: Optional mapping from loaded YAML source paths to
                parsed Webots backend configuration.
        """
        super().__init__()
        self.webots_configs = webots_configs or {}
        self._emission_context: WebotsEmissionContext | None = None
        self._python_transformer = PythonTransformer()

    def set_webots_configs(self, configs: dict[Path, WebotsConfig]) -> None:
        """Replace the Webots controller config mapping used during emission.

        Args:
            configs: Mapping from TENNCell source paths to parsed Webots configs.
        """
        self.webots_configs = configs

    def _config_for(self, system: NncSystem) -> WebotsConfig:
        """Return the Webots config associated with a loaded TENNCell system."""
        if system.source_path is None:
            raise ValueError("Webots export requires systems loaded from YAML files")
        try:
            return self.webots_configs[system.source_path]
        except KeyError as e:
            raise ValueError(
                f"Missing Webots configuration for '{system.source_path}'"
            ) from e

    def get_file_extension(self) -> str:
        """Return the generated Webots controller file extension."""
        return ".py"

    def transform(self, system: NncSystem) -> str:
        """Transform a TENNCell system into a Webots Python controller.

        Args:
            system: Resolved TENNCell system loaded from YAML.

        Returns:
            Generated Python controller source.

        Raises:
            ValueError: If the system was not loaded from YAML, no Webots config
                exists for the source file, or bindings do not match the model.
        """
        self.reset()
        config = self._config_for(system)
        self._validate_configuration(system, config)
        self._emission_context = WebotsEmissionContext(system=system, config=config)

        embedded_python = self._python_transformer.transform(system, include_main=False)
        self.add_line('"""Generated Webots controller from TENNCell system."""')
        self.add_line("from controller import Robot")
        self.add_line()
        for line in embedded_python.splitlines():
            self.add_line(line)
        self.add_line()
        self.add_line(f"# Webots controller: {config.controller_name}")
        self.add_line()
        self._emit_main()
        return self.get_output() + "\n"

    def _validate_configuration(self, system: NncSystem, config: WebotsConfig) -> None:
        """Validate that Webots mappings target existing TENNCell variables."""
        known_variables = set(system.variables.keys())
        for variable, binding in config.bindings.items():
            if variable not in known_variables:
                raise ValueError(
                    f"Webots configuration references unknown TENNCell variable '{variable}'"
                )
            if binding.read_method is None and binding.write_method is None:
                raise ValueError(
                    f"Webots binding '{variable}' must define a read or write method"
                )
        for variable in config.init.keys():
            if variable not in known_variables:
                raise ValueError(
                    f"Webots configuration references unknown TENNCell variable '{variable}'"
                )
            binding = config.bindings.get(variable)
            if binding is None:
                raise ValueError(f"Webots init references unknown binding '{variable}'")
            if binding.write_method is None:
                raise ValueError(
                    f"Webots init references '{variable}' without a write method"
                )

        for variable in system.input_variables.keys():
            binding = config.bindings.get(variable)
            if binding is None:
                raise ValueError(
                    f"Webots configuration is missing an input binding for '{variable}'"
                )
            if binding.read_method is None:
                raise ValueError(
                    f"Webots input binding '{variable}' must define a read method"
                )

        for variable in system.output_variables.keys():
            binding = config.bindings.get(variable)
            if binding is None:
                raise ValueError(
                    f"Webots configuration is missing an output binding for '{variable}'"
                )
            if binding.write_method is None:
                raise ValueError(
                    f"Webots output binding '{variable}' must define a write method"
                )

    def _emit_main(self) -> None:
        assert self._emission_context is not None
        config = self._emission_context.config
        system = self._emission_context.system

        self.add_line("def main():")
        self.add_line("robot = Robot()", 1)
        if config.timestep is None:
            self.add_line("timestep = int(robot.getBasicTimeStep())", 1)
        else:
            self.add_line(f"timestep = {config.timestep}", 1)
        self.add_line("nnc = NncSystem()", 1)
        self.add_line()

        self.add_line("devices = {", 1)
        for variable, binding in config.bindings.items():
            self.add_line(
                f"'{variable}': robot.getDevice({binding.device!r}),",
                2,
            )
        self.add_line("}", 1)

        read_bindings = {
            variable: binding
            for variable, binding in config.bindings.items()
            if variable in system.input_variables and binding.read_method is not None
        }
        if read_bindings:
            for variable in read_bindings:
                self.add_line(
                    f"if hasattr(devices['{variable}'], 'enable'):",
                    1,
                )
                self.add_line(
                    f"devices['{variable}'].enable(timestep)",
                    2,
                )
            self.add_line()

        if config.init:
            for variable, value in config.init.items():
                binding = config.bindings[variable]
                assert binding.write_method is not None
                self.add_line(
                    f"devices['{variable}'].{binding.write_method}({self._format_webots_value(value)})",
                    1,
                )
            self.add_line()

        self.add_line("while robot.step(timestep) != -1:", 1)
        if system.input_variables:
            self.add_line("inputs = {", 2)
            for variable in system.input_variables.keys():
                binding = config.bindings[variable]
                assert binding.read_method is not None
                self.add_line(
                    f"'{variable}': float(devices['{variable}'].{binding.read_method}()),",
                    3,
                )
            self.add_line("}", 2)
            self.add_line("nnc.step(inputs)", 2)
        else:
            self.add_line("nnc.step()", 2)
        self.add_line("variables = nnc.get_variables()", 2)
        if system.output_variables:
            for variable in system.output_variables.keys():
                binding = config.bindings[variable]
                assert binding.write_method is not None
                self.add_line(
                    f"devices['{variable}'].{binding.write_method}(variables['{variable}'])",
                    2,
                )
        else:
            self.add_line("pass", 2)
        self.add_line()
        self.add_line("if __name__ == '__main__':")
        self.add_line("main()", 1)

    @staticmethod
    def _format_webots_value(value: object) -> str:
        """Format a YAML initialization value as Python source text."""
        if isinstance(value, float):
            if value == float("inf"):
                return "float('inf')"
            if value == float("-inf"):
                return "float('-inf')"
            if value != value:
                return "float('nan')"
        return repr(value)
