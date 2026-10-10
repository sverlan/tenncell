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
        self.warnings = list(config.warnings)
        self._emission_context = WebotsEmissionContext(system=system, config=config)

        embedded_python = self._python_transformer.transform(system, include_main=False)
        self.add_line('"""Generated Webots controller from TENNCell system."""')
        if config.csv is not None:
            self.add_line("import csv")
        self.add_line("from controller import Robot")
        self.add_line()
        if config.csv is not None:
            self._emit_csv_format_function()
            self.add_line()
        for line in embedded_python.splitlines():
            self.add_line(line)
        self.add_line()
        self.add_line(f"# Webots controller: {config.controller_name}")
        self.add_line()
        if self._emit_code("module", 0):
            self.add_line()
        self._emit_main()
        return self.get_output() + "\n"

    def _validate_configuration(self, system: NncSystem, config: WebotsConfig) -> None:
        """Validate that Webots mappings target existing TENNCell variables.

        Errors start with the YAML location (``file:line: ``) of the binding,
        ``init`` entry or CSV list they concern, when the parser recorded it.
        """
        known_variables = set(system.variables.keys())
        for variable, binding in config.bindings.items():
            at = config.at("bindings", variable)
            if variable not in known_variables:
                raise ValueError(
                    f"{at}Webots configuration references unknown TENNCell "
                    f"variable '{variable}'"
                )
            if binding.read_method is None and binding.write_method is None:
                raise ValueError(
                    f"{at}Webots binding '{variable}' must define a read or write method"
                )
        for variable in config.init.keys():
            at = config.at("init", variable)
            if variable not in known_variables:
                raise ValueError(
                    f"{at}Webots configuration references unknown TENNCell "
                    f"variable '{variable}'"
                )
            init_binding = config.bindings.get(variable)
            if init_binding is None:
                raise ValueError(
                    f"{at}Webots init references unknown binding '{variable}'"
                )
            if init_binding.write_method is None:
                raise ValueError(
                    f"{at}Webots init references '{variable}' without a write method"
                )
        if config.csv is not None:
            for variable in config.csv.variables:
                if variable not in known_variables:
                    raise ValueError(
                        f"{config.at('csv', 'variables')}Webots CSV configuration "
                        f"references unknown TENNCell variable '{variable}'"
                    )

        for variable in system.input_variables.keys():
            input_binding = config.bindings.get(variable)
            if input_binding is None:
                raise ValueError(
                    f"{config.at('bindings')}Webots configuration is missing an "
                    f"input binding for '{variable}'"
                )
            if input_binding.read_method is None:
                raise ValueError(
                    f"{config.at('bindings', variable)}Webots input binding "
                    f"'{variable}' must define a read method"
                )

        for variable in system.output_variables.keys():
            output_binding = config.bindings.get(variable)
            if output_binding is None:
                raise ValueError(
                    f"{config.at('bindings')}Webots configuration is missing an "
                    f"output binding for '{variable}'"
                )
            if output_binding.write_method is None:
                raise ValueError(
                    f"{config.at('bindings', variable)}Webots output binding "
                    f"'{variable}' must define a write method"
                )

        # Last, so the more basic binding errors above are reported first.
        if "setup" not in config.code:
            for variable, binding in config.bindings.items():
                if binding.device is None:
                    raise ValueError(
                        f"{config.at('bindings', variable)}Webots binding "
                        f"'{variable}' has no device, so webots.code.setup must "
                        f"provide devices['{variable}']"
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
            if binding.device is None:
                self.add_line(f"'{variable}': None,  # virtual: set by setup code", 2)
            else:
                self.add_line(
                    f"'{variable}': robot.getDevice({binding.device!r}),",
                    2,
                )
        self.add_line("}", 1)
        # Right after the devices exist: setup code may add methods to them
        # that enable, init writes and the loop then call, and provides the
        # virtual devices.
        if self._emit_code("setup", 1):
            self.add_line()
        virtual = [
            variable
            for variable, binding in config.bindings.items()
            if binding.device is None
        ]
        for variable in virtual:
            self.add_line(f"if devices['{variable}'] is None:", 1)
            self.add_line(
                f"raise RuntimeError(\"Webots binding '{variable}' has no device: "
                f"webots.code.setup must set devices['{variable}']\")",
                2,
            )
        if virtual:
            self.add_line()

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

        if config.csv is not None:
            header = [
                *(["_step"] if config.csv.include_step else []),
                *(["_time"] if config.csv.include_time else []),
                *config.csv.variables,
            ]
            self.add_line(f"csv_file = open({config.csv.file!r}, 'w', newline='')", 1)
            self.add_line(
                f"csv_writer = csv.writer(csv_file, delimiter={config.csv.delimiter!r})",
                1,
            )
            self.add_line(f"csv_writer.writerow({header!r})", 1)
            self.add_line("step_index = 0", 1)
            if config.csv.include_initial:
                self.add_line("variables = nnc.get_variables()", 1)
                self._emit_csv_row(1)
            self.add_line()

        # With a CSV log or shutdown code, the loop runs in try/finally: the
        # log is closed and the shutdown code runs also after an error
        # (which is then raised again).
        cleanup = config.csv is not None or "shutdown" in config.code
        loop = 2 if cleanup else 1
        body = loop + 1
        if cleanup:
            self.add_line("try:", 1)
        self.add_line("while robot.step(timestep) != -1:", loop)
        if system.input_variables:
            self.add_line("inputs = {", body)
            for variable in system.input_variables.keys():
                binding = config.bindings[variable]
                assert binding.read_method is not None
                self.add_line(
                    f"'{variable}': float(devices['{variable}'].{binding.read_method}()),",
                    body + 1,
                )
            self.add_line("}", body)
            self._emit_code("before_step", body)
            self.add_line("nnc.step(inputs)", body)
        else:
            self._emit_code("before_step", body)
            self.add_line("nnc.step()", body)
        self.add_line("variables = nnc.get_variables()", body)
        if config.csv is not None:
            self.add_line("step_index += 1", body)
            self._emit_csv_row(body, after_step=True)
        self._emit_code("after_step", body)
        if system.output_variables:
            for variable in system.output_variables.keys():
                binding = config.bindings[variable]
                assert binding.write_method is not None
                self.add_line(
                    f"devices['{variable}'].{binding.write_method}(variables['{variable}'])",
                    body,
                )
        elif "after_step" not in config.code:
            self.add_line("pass", body)
        if cleanup:
            self.add_line("finally:", 1)
            if config.csv is not None:
                self.add_line("csv_file.close()", 2)
            else:
                # The shutdown code may be only comments (it is not parsed).
                self.add_line("pass", 2)
            self._emit_code("shutdown", 2)
        self.add_line()
        self.add_line("if __name__ == '__main__':")
        self.add_line("main()", 1)

    def _emit_code(self, point: str, indent: int) -> bool:
        """Paste the user code of ``point`` between marker comments; return
        whether there was any."""
        assert self._emission_context is not None
        block = self._emission_context.config.code.get(point)
        if block is None:
            return False
        self.add_line(f"# webots code: {point} ({block.source})", indent)
        for line in block.text.splitlines():
            # Blank lines stay empty (no trailing indentation).
            self.add_line(line, indent if line.strip() else 0)
        self.add_line(f"# end webots code: {point}", indent)
        return True

    def _emit_csv_row(self, indent: int, after_step: bool = False) -> None:
        """Emit one CSV row write for the current Webots variable snapshot.

        After a step, input variables log the value the step received
        (``inputs``), as ``nnc-verify --inputs`` rows do: the post-step value
        of an input that a rule consumed is 0.
        """
        assert self._emission_context is not None
        csv_config = self._emission_context.config.csv
        assert csv_config is not None
        received = (
            set(self._emission_context.system.input_variables) if after_step else set()
        )

        def source(variable: str) -> str:
            return "inputs" if variable in received else "variables"

        row_items = [
            *(["step_index"] if csv_config.include_step else []),
            *(
                [f"format_csv_value(robot.getTime(), {csv_config.precision!r})"]
                if csv_config.include_time
                else []
            ),
            *[
                f"format_csv_value({source(variable)}[{variable!r}], {csv_config.precision!r})"
                for variable in csv_config.variables
            ],
        ]
        self.add_line(f"csv_writer.writerow([{', '.join(row_items)}])", indent)
        self.add_line("csv_file.flush()", indent)

    def _emit_csv_format_function(self) -> None:
        """Emit the Webots CSV value formatter."""
        self.add_line("def format_csv_value(value, precision=None):")
        self.add_line('"""Format one value for CSV output."""', 1)
        self.add_line(
            "if precision is not None and isinstance(value, (int, float)) "
            "and not isinstance(value, bool):",
            1,
        )
        self.add_line('return f"{value:.{precision}f}"', 2)
        self.add_line("return str(value)", 1)

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
