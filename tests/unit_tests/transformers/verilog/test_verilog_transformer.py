"""Tests for VerilogTransformer output contracts."""

from pathlib import Path

import pytest

from nnc.cli_transform import _collect_import_closure, _parse_verilog_configs
from nnc.model.system import NncSystem
from nnc.transformers import VerilogTransformer


FIXTURE_ROOT = (
    Path(__file__).resolve().parents[3] / "fixtures" / "transformers" / "verilog"
)
INPUT_ROOT = FIXTURE_ROOT / "input"
EXPECTED_ROOT = FIXTURE_ROOT / "expected"


def load_verilog_system(
    file_path: Path, import_paths: list[str] | None = None
) -> tuple[NncSystem, VerilogTransformer]:
    raw_data_cache = {}
    system = NncSystem.from_yaml(
        str(file_path), import_paths=import_paths or [], _raw_data_cache=raw_data_cache
    )
    transformer = VerilogTransformer(
        _parse_verilog_configs(
            _collect_import_closure(system), raw_data_cache, import_paths or []
        )
    )
    return system, transformer


def read_fixture(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def normalize_output(text: str) -> str:
    return text if text.endswith("\n") else text + "\n"


def assert_matches_fixture(
    system_file: Path, expected_file: Path, import_paths: list[str] | None = None
) -> None:
    system, transformer = load_verilog_system(system_file, import_paths)
    result = normalize_output(transformer.transform(system))
    expected = normalize_output(read_fixture(expected_file))
    assert result == expected


class TestVerilogTransformer:
    def test_transform_wraps_module_with_default_nettype_guards(self):
        assert_matches_fixture(INPUT_ROOT / "simple.yaml", EXPECTED_ROOT / "simple.sv")

    def test_transform_emits_imports_externals_and_conversions(self):
        assert_matches_fixture(
            INPUT_ROOT / "imports_externals" / "controller.yaml",
            EXPECTED_ROOT / "imports_externals" / "controller.sv",
            [str(INPUT_ROOT / "imports_externals")],
        )

    def test_transform_rejects_unsupported_function_calls(self):
        system = NncSystem.from_yaml(str(INPUT_ROOT / "bad.yaml"))

        with pytest.raises(ValueError, match="function calls"):
            VerilogTransformer().transform(system)

    def test_zero_reset_mode_omits_used_signals(self):
        assert_matches_fixture(
            INPUT_ROOT / "zero_reset.yaml", EXPECTED_ROOT / "zero_reset.sv"
        )

    def test_top_ports_apply_boundary_conversions_for_same_named_io(self):
        assert_matches_fixture(INPUT_ROOT / "top_io.yaml", EXPECTED_ROOT / "top_io.sv")

    def test_import_connection_uses_local_state_for_unqualified_variable(self):
        assert_matches_fixture(
            INPUT_ROOT / "import_connection" / "root.yaml",
            EXPECTED_ROOT / "import_connection" / "root.sv",
            [str(INPUT_ROOT / "import_connection")],
        )

    def test_unsigned_real_encoding_emits_unsigned_fixed_storage_and_literals(self):
        assert_matches_fixture(
            INPUT_ROOT / "unsigned_fixed.yaml", EXPECTED_ROOT / "unsigned_fixed.sv"
        )

    def test_zero_reset_mode_preserves_input_ports_in_next_state(self):
        assert_matches_fixture(
            INPUT_ROOT / "zero_reset_input.yaml", EXPECTED_ROOT / "zero_reset_input.sv"
        )

    def test_helper_generated_literals_are_emitted(self):
        assert_matches_fixture(
            INPUT_ROOT / "helper_generated_literals" / "root.yaml",
            EXPECTED_ROOT / "helper_generated_literals" / "root.sv",
            [str(INPUT_ROOT / "helper_generated_literals")],
        )

    def test_external_output_connection_to_top_port_is_emitted(self):
        assert_matches_fixture(
            INPUT_ROOT / "external_output_connection" / "root.yaml",
            EXPECTED_ROOT / "external_output_connection" / "root.sv",
            [str(INPUT_ROOT / "external_output_connection")],
        )

    def test_external_output_connection_to_local_variable_is_emitted(self):
        assert_matches_fixture(
            INPUT_ROOT / "external_output_wire" / "root.yaml",
            EXPECTED_ROOT / "external_output_wire" / "root.sv",
            [str(INPUT_ROOT / "external_output_wire")],
        )

    def test_logic_vector_top_output_uses_shifted_fixed_bits(self):
        assert_matches_fixture(
            INPUT_ROOT / "logic_vector.yaml", EXPECTED_ROOT / "logic_vector.sv"
        )

    def test_multiple_logic_vector_output_widths_use_distinct_helpers(self):
        assert_matches_fixture(
            INPUT_ROOT / "logic_vectors.yaml", EXPECTED_ROOT / "logic_vectors.sv"
        )

    def test_recursive_if_and_fsm_yaml_export_to_verilog(self):
        assert_matches_fixture(INPUT_ROOT / "fsm_if.yaml", EXPECTED_ROOT / "fsm_if.sv")

    def test_missing_child_ports_are_inferred_from_real_encoding(self):
        assert_matches_fixture(
            INPUT_ROOT / "inferred_ports.yaml",
            EXPECTED_ROOT / "inferred_ports.sv",
        )

    def test_imported_child_ports_use_declared_port_conversions(self):
        assert_matches_fixture(
            INPUT_ROOT / "blink_uart_boundary" / "root.yaml",
            EXPECTED_ROOT / "blink_uart_boundary" / "root.sv",
            [str(INPUT_ROOT / "blink_uart_boundary")],
        )
