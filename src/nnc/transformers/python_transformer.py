"""Python transformer for converting TENNCell AST to Python code."""

from pathlib import Path

from .base_transformer import BaseTransformer
from .python.emission_context import PythonEmissionContext
from .python import PythonCoreEmitter, PythonCsvScriptEmitter, PythonExpressionEmitter
from ..inputs.yaml.errors import as_yaml_located_error
from ..model.system import NncSystem


class PythonTransformer(
    PythonCoreEmitter, PythonCsvScriptEmitter, PythonExpressionEmitter, BaseTransformer
):
    """Transformer that converts TENNCell systems to Python code."""

    def __init__(self):
        super().__init__()
        self._emission_context: PythonEmissionContext | None = None

    def get_file_extension(self) -> str:
        """Get the file extension for Python files."""
        return ".py"

    def transform(self, system: NncSystem, *, include_main: bool = True) -> str:
        """Transform a TENNCell system to Python code.

        Args:
            system: The TENNCell system to transform
            include_main: Whether to emit the CSV-oriented ``main()`` wrapper.

        Returns:
            Python code as a string
        """
        try:
            self.reset()
            self._current_system = None
            self._uses_random = False
            ctx = PythonEmissionContext(
                system=system,
                composed_mode=bool(getattr(system, "imports", [])),
            )
            self._emission_context = ctx

            system_dict = getattr(system, "__dict__", {})
            if system_dict.get("imports"):
                return self._transform_composed(system, ctx, include_main=include_main)

            self.add_line("# Generated Python code from TENNCell system")
            self.add_line("import math")
            self.add_line()

            self.add_line("class NncSystem:")
            self.add_line("def __init__(self):", 1)

            emitted_init = self._emit_variable_initializers(
                system, 2, track_declarations=True, ctx=ctx
            )
            if not emitted_init:
                raise ValueError(
                    "Python generation requires at least one model variable or "
                    "semantic import; nothing to generate"
                )

            input_vars = self._input_vars(system)
            output_vars = self._output_vars(system)

            self.add_line()

            var_names = sorted(ctx.variable_declarations)
            signature = ", inputs" if input_vars else ""
            self._emit_step_method(
                system,
                var_names,
                input_vars,
                output_vars,
                indent=1,
                signature=signature,
                coerce_inputs=False,
                input_value_wrapper="inputs['{var_name}']",
                include_docstring=True,
            )

            self.add_line()
            self._emit_get_variables(var_names, 1)

            if include_main:
                self.add_line()
                self.add_line()
                self._emit_main_function(system)

            self._add_random_import()
            return self.get_output()
        except Exception as error:
            raise as_yaml_located_error(
                error,
                getattr(system, "source_path", None),
                self._source_line(system),
            ) from error

    def _transform_composed(
        self,
        system: NncSystem,
        ctx: PythonEmissionContext | None = None,
        *,
        include_main: bool = True,
    ) -> str:
        try:
            ctx = ctx or self._emission_context
            assert ctx is not None
            self.add_line("# Generated Python code from composed TENNCell system")
            self.add_line("import math")
            self.add_line()

            self._collect_class_names(system, ctx)
            self._emit_base_class()

            self._emit_module_class(system, ctx)
            root_base = self._class_name(system, ctx)
            self.add_line(f"class NncSystem({root_base}):")
            self.add_line("pass", 1)
            self.add_line()

            if include_main:
                self._emit_main_function(system)
            self._add_random_import()
            return self.get_output()
        except Exception as error:
            raise as_yaml_located_error(
                error,
                getattr(system, "source_path", None),
                self._source_line(system),
            ) from error

    def _add_random_import(self) -> None:
        """Add ``import random`` after ``import math`` when ``random()`` was emitted."""
        if self._uses_random:
            self.output.insert(self.output.index("import math") + 1, "import random")

    def _collect_class_names(
        self, system: NncSystem, ctx: PythonEmissionContext | None = None
    ):
        ctx = ctx or self._emission_context
        assert ctx is not None
        ordered = self._module_closure(system)
        used: dict[str, int] = {}
        for module in ordered:
            assert module.source_path is not None
            base = self._sanitize_class_name(module.module_config.name)
            count = used.get(base, 0) + 1
            used[base] = count
            suffix = "" if count == 1 else f"_{count}"
            ctx.class_names[module.source_path] = f"_Module_{base}{suffix}"

    def _module_closure(self, system: NncSystem) -> list[NncSystem]:
        ordered: list[NncSystem] = []
        seen: set[Path] = set()

        def visit(module: NncSystem):
            assert module.source_path is not None
            if module.source_path in seen:
                return
            seen.add(module.source_path)
            for item in module.imports:
                assert item.system is not None
                visit(item.system)
            ordered.append(module)

        visit(system)
        return ordered

    def _sanitize_class_name(self, name: str) -> str:
        pieces = []
        for char in name:
            pieces.append(char if char.isalnum() else "_")
        sanitized = "".join(pieces).strip("_") or "Nnc"
        if sanitized[0].isdigit():
            sanitized = f"_{sanitized}"
        return sanitized

    def _class_name(
        self, system: NncSystem, ctx: PythonEmissionContext | None = None
    ) -> str:
        ctx = ctx or self._emission_context
        assert ctx is not None
        assert system.source_path is not None
        return ctx.class_names[system.source_path]

    def _source_line(self, system: NncSystem) -> int | None:
        """Return a best-effort YAML line for a backend error."""

        locations = getattr(system, "locations", None)
        if locations is None:
            return 1
        line = locations.first_line_under("module")
        if line is not None:
            return line
        return locations.first_line_under()
