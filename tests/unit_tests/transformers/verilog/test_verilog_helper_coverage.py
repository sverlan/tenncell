"""Internal contract tests for Verilog helper emitters."""

from pathlib import Path

import pytest

from nnc.cli_transform import _collect_import_closure, _parse_verilog_configs
from nnc.inputs.yaml.module_config import ImportConfig, ModuleConfig
from nnc.model.system import NncSystem
from nnc.parser.ast import Variable
from nnc.parser.ast.value import FloatValue
from nnc.transformers import VerilogTransformer
from nnc.transformers.verilog.generation.context import VerilogEmissionContext
from nnc.transformers.verilog.hardware_config import (
    RealEncoding,
    VerilogHardwareConfig,
    VerilogFixedPointEncoding,
    VerilogFixedPointTypeInfo,
    VerilogLogicEncoding,
    VerilogLogicTypeInfo,
)


FIXTURE_ROOT = (
    Path(__file__).resolve().parents[3] / "fixtures" / "transformers" / "verilog"
)
INPUT_ROOT = FIXTURE_ROOT / "input"


def load_verilog_system(file_path: Path, import_paths: list[str] | None = None):
    from nnc.model.system import NncSystem

    raw_data_cache = {}
    system = NncSystem.from_yaml(
        str(file_path), import_paths=import_paths or [], _raw_data_cache=raw_data_cache
    )
    transformer = VerilogTransformer(
        _parse_verilog_configs(
            _collect_import_closure(system), raw_data_cache, import_paths or []
        )
    )
    (
        top_ports,
        external_input_bindings,
        external_output_bindings,
        import_output_bindings,
    ) = transformer._build_binding_maps(system)
    transformer._emission_context = VerilogEmissionContext(
        system=system,
        config=transformer._config_for(system),
        local_variables=sorted(system.variables.keys()),
        top_ports=top_ports,
        external_input_bindings=external_input_bindings,
        external_output_bindings=external_output_bindings,
        import_output_bindings=import_output_bindings,
    )
    return system, transformer


class TestVerilogHelperCoverage:
    def test_conversion_emitter_helpers(self):
        transformer = VerilogTransformer()
        assert transformer._fixed_storage_decl(1, False) == "logic [0:0]"
        assert transformer._fixed_storage_decl(4, True) == "logic signed [3:0]"
        assert transformer._encode_float(1.5, 8, 2, True) == "8'sd6"
        assert transformer._encode_float(-1.0, 4, 0, False) == "4'd15"
        assert transformer._sanitize_literal_value(-1.5) == "NEG_1_5"
        assert transformer._conversion_descriptor("fixed", 8, True, 2) == "sfixed_8_2"
        assert transformer._conversion_descriptor("logic", 8, False, 0) == "logic_8"
        assert transformer._conversion_descriptor("logic", 1, False, 0) == "logic"
        assert transformer._type_decl("logic", 1, False) == "logic"
        assert transformer._type_decl("logic", 4, False) == "logic [3:0]"
        assert transformer._type_decl("fixed", 4, True) == "logic signed [3:0]"
        assert transformer._type_info_encoding(
            VerilogLogicTypeInfo(kind="logic", width=8, signed=False)
        ) == VerilogLogicEncoding(kind="logic", width=8, signed=False)
        assert transformer._type_info_encoding(
            VerilogFixedPointTypeInfo(
                kind="fixed_point", width=8, frac_bits=3, signed=True
            )
        ) == VerilogFixedPointEncoding(kind="fixed", width=8, signed=True, frac_bits=3)
        assert (
            transformer._type_info_decl(
                VerilogLogicTypeInfo(kind="logic", width=8, signed=False)
            )
            == "logic [7:0]"
        )
        assert (
            transformer._type_info_decl(
                VerilogFixedPointTypeInfo(
                    kind="fixed_point", width=8, frac_bits=3, signed=True
                )
            )
            == "logic signed [7:0]"
        )

        literal_transformer = VerilogTransformer()
        literal_transformer._emission_context = VerilogEmissionContext(
            system=NncSystem(),
            config=VerilogHardwareConfig(
                real_encoding=RealEncoding("fixed_point", True, 8, 2)
            ),
            literal_params={(1.0, 8, 2, True): "_VAL_1_0"},
        )
        assert literal_transformer._literal_param_name(1.0, 8, 2, True) == "_VAL_1_0"
        assert (
            literal_transformer._literal_param_name(1.0, 8, 3, True) == "_VAL_1_0_Q5_3"
        )
        assert literal_transformer._emit_literal_params() != ""
        assert literal_transformer._emit_conversion_helpers() == ""

        literal_transformer._emission_context.conversion_helpers = {
            ("fixed", 8, True, 2, "logic", 1, False, 0): "conv_test",
        }
        conversion_helpers = literal_transformer._emit_conversion_helpers()
        assert "function automatic logic conv_test(" in conversion_helpers
        assert "conv_test = (value != '0);" in conversion_helpers

    def test_conversion_expression_matrix(self):
        transformer = VerilogTransformer()
        transformer._emission_context = VerilogEmissionContext(
            system=NncSystem(),
            config=VerilogHardwareConfig(),
        )

        assert (
            transformer._conversion_expression("fixed", 8, True, 2, "fixed", 8, True, 4)
            == "(value <<< 2)"
        )
        assert (
            transformer._conversion_expression("fixed", 8, True, 4, "fixed", 8, True, 2)
            == "(value >>> 2)"
        )
        assert (
            transformer._conversion_expression("fixed", 8, True, 2, "fixed", 8, True, 2)
            == "value"
        )
        assert (
            transformer._conversion_expression("fixed", 8, True, 0, "fixed", 8, True, 0)
            == "value"
        )
        assert (
            transformer._conversion_expression(
                "logic", 8, False, 0, "fixed", 8, True, 3
            )
            == "(value <<< 3)"
        )
        assert (
            transformer._conversion_expression(
                "logic", 8, False, 0, "fixed", 8, True, 0
            )
            == "value"
        )
        assert (
            transformer._conversion_expression(
                "logic", 8, False, 0, "fixed", 8, True, 3
            )
            == "(value <<< 3)"
        )
        assert (
            transformer._conversion_expression("fixed", 8, True, 2, "logic", 8, True, 0)
            == "(value >>> 2)"
        )
        assert (
            transformer._conversion_expression("fixed", 8, True, 0, "logic", 8, True, 0)
            == "value"
        )
        assert (
            transformer._conversion_expression(
                "logic", 1, False, 0, "logic", 1, False, 0
            )
            == "value"
        )
        assert (
            transformer._conversion_expression(
                "fixed", 8, True, 2, "logic", 1, False, 0
            )
            == "(value != '0)"
        )
        assert (
            transformer._conversion_expression(
                "logic", 1, False, 0, "fixed", 8, True, 3
            )
            == "(value ? _VAL_1_0 : '0)"
        )
        assert (
            transformer._conversion_expression(
                "fixed", 8, True, 2, "logic", 8, False, 0
            )
            == "(value >>> 2)"
        )

        with pytest.raises(ValueError, match="Unsupported conversion"):
            transformer._conversion_expression(
                "bogus", 1, False, 0, "logic", 1, False, 0
            )

    def test_reference_resolver_helpers(self):
        system, transformer = load_verilog_system(
            INPUT_ROOT / "imports_externals" / "controller.yaml",
            [str(INPUT_ROOT / "imports_externals")],
        )

        assert transformer._reference_signal_name("sensor0.level") == "sensor0__level"
        assert transformer._reference_signal("clk") == "clk"
        assert transformer._reference_signal("sensor0.level") == "sensor0__level"
        assert transformer._top_port_config("uart_rx") is not None
        assert transformer._top_port_config("missing") is None

        assert transformer._reference_encoding("clk") == VerilogLogicEncoding(
            kind="logic", width=1, signed=False
        )
        assert transformer._reference_encoding("uart_rx") == VerilogLogicEncoding(
            kind="logic", width=1, signed=False
        )
        assert transformer._reference_encoding(
            "sensor0.level"
        ) == VerilogFixedPointEncoding(kind="fixed", width=24, signed=True, frac_bits=8)
        assert transformer._resolve_connection("0", "logic", 1, False, 0) == "0"
        assert (
            transformer._resolve_connection("unknown", "logic", 1, False, 0)
            == "unknown"
        )
        assert (
            transformer._resolve_connection("alarm", "fixed", 32, True, 16)
            == "conv_logic_32_to_sfixed_32_16(alarm)"
        )
        assert transformer._resolve_connection(
            "alarm", "logic", 1, False, 0
        ).startswith("conv_")
        assert (
            transformer._convert_local_fixed_to_target("alarm", "fixed", 32, True)
            == "state_alarm"
        )
        assert transformer._convert_local_fixed_to_target(
            "alarm", "logic", 1, False
        ).startswith("conv_")
        assert (
            transformer._external_output_to_target(
                "sig", "logic", 1, False, 0, "logic", 1, False, 0
            )
            == "sig"
        )
        assert transformer._external_output_to_target(
            "sig", "logic", 1, False, 0, "fixed", 8, True, 2
        ).startswith("conv_")
        assert (
            transformer._maybe_convert_signal(
                "uart_rx",
                "uart_rx",
                VerilogLogicEncoding(kind="logic", width=1, signed=False),
            )
            == "uart_rx"
        )

        with pytest.raises(ValueError, match="Unknown connection reference"):
            transformer._reference_encoding("uart0.rx_data")

        with pytest.raises(ValueError, match="Signedness mismatch"):
            transformer._maybe_convert_signal(
                "sensor0.level",
                "sensor0__level",
                VerilogFixedPointEncoding(
                    kind="fixed", width=24, signed=False, frac_bits=8
                ),
            )

        assert transformer._maybe_convert_signal(
            "sensor0.level",
            "sensor0__level",
            VerilogLogicEncoding(kind="logic", width=24, signed=False),
        ).startswith("conv_")

        with pytest.raises(ValueError, match="Unknown connection reference"):
            transformer._reference_encoding("missing")

        with pytest.raises(ValueError, match="Unknown connection reference"):
            transformer._reference_encoding("missing.signal")

    def test_reference_resolver_imported_input_and_output_branches(self):
        root = NncSystem()
        root.source_path = Path("root.yaml")
        root.module_config = ModuleConfig(name="root")
        root.variables["alarm"] = Variable("alarm", FloatValue(0.0))
        root.output_variables["alarm"] = root.variables["alarm"]

        child = NncSystem()
        child.source_path = Path("sensor.yaml")
        child.module_config = ModuleConfig(name="sensor")
        child.variables["raw"] = Variable("raw", FloatValue(0.0))
        child.variables["level"] = Variable("level", FloatValue(0.0))
        child.input_variables["raw"] = child.variables["raw"]
        child.output_variables["level"] = child.variables["level"]

        root.imports = [
            ImportConfig(
                module="sensor.yaml",
                alias="sensor0",
                system=child,
                connections={"raw": "alarm"},
            )
        ]

        transformer = VerilogTransformer(
            {
                root.source_path: VerilogHardwareConfig(
                    real_encoding=RealEncoding("fixed_point", True, 32, 16)
                ),
                child.source_path: VerilogHardwareConfig(
                    real_encoding=RealEncoding("fixed_point", True, 24, 8)
                ),
            }
        )
        transformer._emission_context = VerilogEmissionContext(
            system=root,
            config=transformer._config_for(root),
            local_variables=["alarm"],
        )

        assert transformer._reference_encoding(
            "sensor0.raw"
        ) == VerilogFixedPointEncoding(kind="fixed", width=24, signed=True, frac_bits=8)
        assert transformer._reference_encoding(
            "sensor0.level"
        ) == VerilogFixedPointEncoding(kind="fixed", width=24, signed=True, frac_bits=8)
        assert (
            transformer._resolve_connection("sensor0.raw", "fixed", 24, True, 8)
            == "sensor0__raw"
        )

    def test_blink_uart_typed_example_uses_internal_type_hints(self):
        example_root = INPUT_ROOT / "blink_uart_typed" / "blink_uart_typed.yaml"
        system, transformer = load_verilog_system(
            example_root, [str(example_root.parent)]
        )
        output = transformer.transform(system)
        assert "logic [24:0] state_counter;" in output
        assert "state_counter + 25'd1" in output
        assert "(state_counter >= 25'd27000000)" in output

    def test_internal_types_reject_interface_variables(self, tmp_path):
        source = tmp_path / "typed_interface.yaml"
        source.write_text(
            "\n".join(
                [
                    "module:",
                    "  name: typed_interface",
                    "cells:",
                    "  - id: 1",
                    "    contents:",
                    "      - x = 0",
                    "    output: [x]",
                    "rules:",
                    "  - 1 -> x",
                    "verilog:",
                    "  real_encoding:",
                    "    kind: fixed_point",
                    "    signed: false",
                    "    width: 8",
                    "    frac_bits: 0",
                    "  types:",
                    "    x:",
                    "      kind: logic",
                    "      width: 1",
                ]
            ),
            encoding="utf-8",
        )

        system, transformer = load_verilog_system(source)

        with pytest.raises(ValueError, match="must not describe an interface variable"):
            transformer.transform(system)
