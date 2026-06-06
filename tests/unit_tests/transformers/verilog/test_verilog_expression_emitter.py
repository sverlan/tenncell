"""Internal contract tests for Verilog expression emission."""

from pathlib import Path

import pytest

from nnc.cli_transform import _collect_import_closure, _parse_verilog_configs
from nnc.parser.ast import (
    BooleanAndExpression,
    BooleanConstantExpression,
    BooleanEqualTestExpression,
    BooleanGreaterEqualTestExpression,
    BooleanGreaterTestExpression,
    BooleanLessEqualTestExpression,
    BooleanLessTestExpression,
    BooleanNotEqualTestExpression,
    BooleanNotExpression,
    BooleanOrExpression,
    ConstantExpression,
    DifferenceExpression,
    DivisionExpression,
    IntDivisionExpression,
    IntMultiplicationExpression,
    MultiplicationExpression,
    ReferenceExpression,
    SumExpression,
    UnaryMinusExpression,
    Variable,
    VariableExpression,
)
from nnc.parser.ast.expression import FunctionCallExpression
from nnc.parser.ast.value import FloatValue
from nnc.model.system import NncSystem
from nnc.transformers import VerilogTransformer
from nnc.transformers.verilog.generation.context import VerilogEmissionContext
from nnc.transformers.verilog.hardware_config import VerilogLogicTypeInfo


FIXTURE_ROOT = (
    Path(__file__).resolve().parents[3] / "fixtures" / "transformers" / "verilog"
)
INPUT_ROOT = FIXTURE_ROOT / "input"


def load_verilog_system(file_path: Path, import_paths: list[str] | None = None):
    raw_data_cache = {}
    system = NncSystem.from_yaml(
        str(file_path), import_paths=import_paths or [], _raw_data_cache=raw_data_cache
    )
    transformer = VerilogTransformer(
        _parse_verilog_configs(
            _collect_import_closure(system), raw_data_cache, import_paths or []
        )
    )
    transformer._emission_context = VerilogEmissionContext(
        system=system,
        config=transformer._config_for(system),
        local_variables=sorted(system.variables.keys()),
    )
    return system, transformer


class TestVerilogExpressionEmitter:
    def test_validate_supported_system_rejects_unsupported_constructs(self):
        system_file = INPUT_ROOT / "bad.yaml"
        system = NncSystem.from_yaml(str(system_file))
        transformer = VerilogTransformer()

        with pytest.raises(ValueError, match="function calls"):
            transformer._validate_supported_system(system)

    def test_validate_expression_and_visitors(self):
        _, transformer = load_verilog_system(
            INPUT_ROOT / "imports_externals" / "controller.yaml",
            [str(INPUT_ROOT / "imports_externals")],
        )
        blink_system, blink_transformer = load_verilog_system(
            INPUT_ROOT / "blink_uart_boundary" / "root.yaml",
            [str(INPUT_ROOT / "blink_uart_boundary")],
        )
        transformer._emission_context.local_variables.extend(["x", "y"])
        (
            top_ports,
            external_input_bindings,
            external_output_bindings,
            import_output_bindings,
        ) = blink_transformer._build_binding_maps(blink_system)
        blink_transformer._emission_context = VerilogEmissionContext(
            system=blink_system,
            config=blink_transformer._config_for(blink_system),
            local_variables=sorted(blink_system.variables.keys()),
            top_ports=top_ports,
            external_input_bindings=external_input_bindings,
            external_output_bindings=external_output_bindings,
            import_output_bindings=import_output_bindings,
            resolved_var_types={
                "counter": VerilogLogicTypeInfo(kind="logic", width=25, signed=False),
                "toggle_pulse": VerilogLogicTypeInfo(
                    kind="logic", width=1, signed=False
                ),
            },
        )
        blink_transformer._emission_context.local_variables.extend(["x", "y"])
        x = VariableExpression(Variable("x", FloatValue(1.0)))
        y = VariableExpression(Variable("y", FloatValue(2.0)))

        assert (
            transformer.visit_ConstantExpression(ConstantExpression(FloatValue(1.0)))
            == "_VAL_1_0"
        )
        assert (
            transformer.visit_VariableExpression(
                VariableExpression(Variable("alarm", FloatValue(0.0)))
            )
            == "state_alarm"
        )
        assert transformer.visit_ReferenceExpression(
            ReferenceExpression(["sensor0", "level"])
        ).startswith("conv_")
        assert (
            transformer.visit_SumExpression(SumExpression(x, y))
            == "(state_x + state_y)"
        )
        assert (
            transformer.visit_DifferenceExpression(DifferenceExpression(x, y))
            == "(state_x - state_y)"
        )
        assert transformer.visit_MultiplicationExpression(
            MultiplicationExpression(ConstantExpression(FloatValue(2.0)), x)
        ).startswith("((")
        assert transformer.visit_DivisionExpression(
            DivisionExpression(x, ConstantExpression(FloatValue(2.0)))
        ).startswith("((")
        assert (
            transformer.visit_UnaryMinusExpression(UnaryMinusExpression(x))
            == "(-state_x)"
        )
        assert (
            transformer.visit_IntMultiplicationExpression(
                IntMultiplicationExpression(3, x)
            )
            == "(_VAL_3_0 * state_x)"
        )
        assert (
            transformer.visit_IntDivisionExpression(IntDivisionExpression(3, y))
            == "(state_y / _VAL_3_0)"
        )
        assert (
            transformer.visit_BooleanConstantExpression(BooleanConstantExpression(True))
            == "1'b1"
        )
        assert (
            transformer.visit_BooleanAndExpression(
                BooleanAndExpression(
                    BooleanConstantExpression(True), BooleanConstantExpression(False)
                )
            )
            == "(1'b1 && 1'b0)"
        )
        assert (
            transformer.visit_BooleanOrExpression(
                BooleanOrExpression(
                    BooleanConstantExpression(True), BooleanConstantExpression(False)
                )
            )
            == "(1'b1 || 1'b0)"
        )
        assert (
            transformer.visit_BooleanNotExpression(
                BooleanNotExpression(BooleanConstantExpression(True))
            )
            == "(!1'b1)"
        )
        assert (
            transformer.visit_BooleanLessTestExpression(BooleanLessTestExpression(x, y))
            == "(state_x < state_y)"
        )
        assert (
            transformer.visit_BooleanLessEqualTestExpression(
                BooleanLessEqualTestExpression(x, y)
            )
            == "(state_x <= state_y)"
        )
        assert (
            transformer.visit_BooleanGreaterTestExpression(
                BooleanGreaterTestExpression(x, y)
            )
            == "(state_x > state_y)"
        )
        assert (
            transformer.visit_BooleanGreaterEqualTestExpression(
                BooleanGreaterEqualTestExpression(x, y)
            )
            == "(state_x >= state_y)"
        )
        assert (
            transformer.visit_BooleanEqualTestExpression(
                BooleanEqualTestExpression(x, y)
            )
            == "(state_x == state_y)"
        )
        assert (
            transformer.visit_BooleanNotEqualTestExpression(
                BooleanNotEqualTestExpression(x, y)
            )
            == "(state_x != state_y)"
        )

        assert (
            blink_transformer.visit_BooleanEqualTestExpression(
                BooleanEqualTestExpression(
                    VariableExpression(Variable("uart_ready", FloatValue(0.0))),
                    ConstantExpression(FloatValue(1.0)),
                )
            )
            == "(uart_ready == 1'b1)"
        )
        assert (
            blink_transformer.visit_BooleanGreaterEqualTestExpression(
                BooleanGreaterEqualTestExpression(
                    VariableExpression(Variable("counter", FloatValue(0.0))),
                    ConstantExpression(FloatValue(1.0)),
                )
            )
            == "(state_counter >= 25'd1)"
        )
        assert (
            blink_transformer.visit_SumExpression(
                SumExpression(
                    VariableExpression(Variable("counter", FloatValue(0.0))),
                    ConstantExpression(FloatValue(1.0)),
                )
            )
            == "(state_counter + 25'd1)"
        )

        assert (
            blink_transformer.visit_BooleanEqualTestExpression(
                BooleanEqualTestExpression(
                    VariableExpression(Variable("toggle_pulse", FloatValue(0.0))),
                    ConstantExpression(FloatValue(1.0)),
                )
            )
            == "(state_toggle_pulse == 1'b1)"
        )

        with pytest.raises(
            ValueError, match="Verilog export does not support function calls"
        ):
            transformer._validate_expression(FunctionCallExpression("sin", [x]))

    def test_validate_expression_rejects_unsupported_and_invalid_operations(self):
        transformer = VerilogTransformer()
        valid_constant = ConstantExpression(FloatValue(2.0))
        x = VariableExpression(Variable("x", FloatValue(1.0)))
        y = VariableExpression(Variable("y", FloatValue(2.0)))

        transformer._validate_expression(MultiplicationExpression(valid_constant, y))
        transformer._validate_expression(DivisionExpression(x, valid_constant))

        with pytest.raises(ValueError, match="variable-by-variable multiplication"):
            transformer._validate_expression(MultiplicationExpression(x, y))

        with pytest.raises(ValueError, match="general division"):
            transformer._validate_expression(DivisionExpression(x, y))

        with pytest.raises(ValueError, match="Unsupported expression type"):
            transformer._validate_expression(object())

        with pytest.raises(ValueError, match="Unsupported Verilog node type"):
            transformer.visit(object())
