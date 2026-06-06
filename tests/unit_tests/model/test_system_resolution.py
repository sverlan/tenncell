"""Resolution helper contract tests."""

import pytest

from nnc.inputs.yaml.resolution import parse_reference_expr, resolve_path
from nnc.parser.ast import (
    ConstantExpression,
    ReferenceExpression,
    Variable,
    VariableExpression,
)
from nnc.parser.ast.value import FloatValue


class TestSystemResolution:
    def test_resolve_path_prefers_source_parent(self, tmp_path):
        source = tmp_path / "root" / "controller.yaml"
        source.parent.mkdir(parents=True, exist_ok=True)
        local_target = source.parent / "sensor.yaml"
        local_target.write_text("module:\n  name: sensor\n", encoding="utf-8")

        resolved = resolve_path("sensor.yaml", source, [])

        assert resolved == local_target.resolve()

    def test_resolve_path_falls_back_to_import_paths(self, tmp_path):
        source = tmp_path / "root" / "controller.yaml"
        source.parent.mkdir(parents=True, exist_ok=True)
        import_dir = tmp_path / "lib"
        import_dir.mkdir(parents=True, exist_ok=True)
        target = import_dir / "sensor.yaml"
        target.write_text("module:\n  name: sensor\n", encoding="utf-8")

        resolved = resolve_path("sensor.yaml", source, [import_dir])

        assert resolved == target.resolve()

    def test_resolve_path_unknown_raises(self, tmp_path):
        source = tmp_path / "root" / "controller.yaml"
        source.parent.mkdir(parents=True, exist_ok=True)

        with pytest.raises(ValueError, match="Could not resolve import 'missing.yaml'"):
            resolve_path("missing.yaml", source, [])

    def test_parse_reference_expr_prefers_alias(self):
        aliases = {"alias_x": VariableExpression(Variable("x", FloatValue(1.0)))}
        constants = {"C": FloatValue(2.0)}
        variables = {"x": Variable("x", FloatValue(3.0))}

        assert (
            parse_reference_expr("alias_x", variables, constants, aliases)
            is aliases["alias_x"]
        )

    def test_parse_reference_expr_uses_constant(self):
        constants = {"C": FloatValue(2.0)}

        expr = parse_reference_expr("C", {}, constants, {})

        assert isinstance(expr, ConstantExpression)
        assert expr.value.value == 2.0

    def test_parse_reference_expr_uses_variable(self):
        variable = Variable("x", FloatValue(3.0))

        expr = parse_reference_expr("x", {"x": variable}, {}, {})

        assert isinstance(expr, VariableExpression)
        assert expr.variable is variable

    def test_parse_reference_expr_parses_dotted_reference(self):
        expr = parse_reference_expr("sensor.value", {}, {}, {})

        assert isinstance(expr, ReferenceExpression)
        assert expr.parts == ["sensor", "value"]

    def test_parse_reference_expr_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown reference 'missing'"):
            parse_reference_expr("missing", {}, {}, {})
