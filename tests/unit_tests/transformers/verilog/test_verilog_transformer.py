"""Tests for VerilogTransformer output contracts."""

from pathlib import Path

import shutil

import pytest

from nnc.cli_transform import _collect_import_closure, _parse_verilog_configs
from nnc.model.system import NncSystem
from nnc.inputs.yaml.errors import YamlLocatedError
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


# Small error table (inline by design): model names that would be emitted as
# SystemVerilog keywords. Each case writes the root model (and a child or an
# external header) with the given replacements.
_ENCODING = "real_encoding: {kind: fixed_point, signed: true, width: 16, frac_bits: 8}"
_ROOT = """{module}{constants}{imports}
cells:
  - id: 1
    contents:
      - {var} = 0{extra_vars}
    output: [{var}]
rules:
  - {var} -> {var}
verilog:
  clock: {clock}
  {encoding}
  ports:
    {var}: {{direction: output, kind: fixed, width: 16, signed: true, rename: {rename}}}{externals}
"""
_CHILD = """module:
  name: {child_module}
cells:
  - id: 1
    contents:
      - a = 0, {child_out} = 0
    input: [a]
    output: [{child_out}]
rules:
  - a -> {child_out}
verilog:
  {encoding}
  ports:
    a: {{direction: input, kind: fixed, width: 16, signed: true}}
    {child_out}: {{direction: output, kind: fixed, width: 16, signed: true, rename: {child_rename}}}
"""
_HEADER = """schema:
  name: uart
  ports:
    - {name: clk, direction: input, width: 1, signed: false}
    - {name: ready, direction: output, width: 1, signed: false}
"""
_IMPORT = (
    "\nimports:\n  - module: child.yaml\n    as: {alias}\n    connections: {{a: x}}"
)
_EXTERNAL = (
    "\n  externals:\n    {alias}:\n      header: uart.header.yaml\n"
    "      connections: {{clk: clk, ready: {wire}}}"
)
_DEFAULTS = {
    "module": "",
    "constants": "",
    "imports": "",
    "var": "x",
    "extra_vars": "",
    "clock": "clk",
    "rename": "x_out",
    "externals": "",
    "child_module": "child",
    "child_out": "y",
    "child_rename": "y_out",
}


def test_number_on_an_external_output_is_rejected(tmp_path):
    source = INPUT_ROOT / "external_numbers"
    shutil.copy(source / "dev.header.yaml", tmp_path / "dev.header.yaml")
    text = (source / "root.yaml").read_text(encoding="utf-8")
    (tmp_path / "root.yaml").write_text(
        text.replace("ready: rdy", "ready: 5"), encoding="utf-8"
    )

    with pytest.raises(
        YamlLocatedError,
        match=r"root\.yaml:\d+: verilog\.externals\.dev0\.connections\.ready is an "
        r"output of the external module: connect it to a variable, not a number",
    ):
        load_verilog_system(tmp_path / "root.yaml", [str(tmp_path)])


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        (
            {"module": "module:\n  name: weak"},
            "'weak' is a SystemVerilog keyword and cannot be the module name",
        ),
        (
            {"rename": "cover"},
            "'cover' is a SystemVerilog keyword and cannot be a port name",
        ),
        (
            {"clock": "edge"},
            "'edge' is a SystemVerilog keyword and cannot be a port name",
        ),
        (
            {"constants": "\nconstants:\n  final: 1"},
            "'final' .* cannot be a constant name",
        ),
        (
            {"imports": _IMPORT.format(alias="begin")},
            "'begin' .* cannot be an import alias",
        ),
        (
            {"imports": _IMPORT.format(alias="c0"), "child_module": "weak"},
            "'weak' .* cannot be the name of imported module 'c0'",
        ),
        (
            {"imports": _IMPORT.format(alias="c0"), "child_rename": "within"},
            "'within' .* cannot be a port name of imported module 'c0'",
        ),
        (
            # `table` takes the child's output, so it is a wire of the parent.
            {
                "imports": _IMPORT.format(alias="c0"),
                "child_out": "table",
                "extra_vars": ", table = 0",
            },
            "'table' .* cannot be a variable name",
        ),
        (
            {"externals": _EXTERNAL.format(alias="wait", wire="r")},
            "'wait' .* cannot be an external alias",
        ),
        (
            {
                "externals": _EXTERNAL.format(alias="u0", wire="table"),
                "extra_vars": ", table = 0",
            },
            "'table' .* cannot be a variable name",
        ),
    ],
)
def test_systemverilog_keywords_are_rejected(tmp_path, fields, message):
    values = {**_DEFAULTS, **fields, "encoding": _ENCODING}
    if "extra_vars" not in fields and "externals" in fields:
        values["extra_vars"] = ", r = 0"
    (tmp_path / "child.yaml").write_text(_CHILD.format(**values), encoding="utf-8")
    (tmp_path / "uart.header.yaml").write_text(_HEADER, encoding="utf-8")
    path = tmp_path / "model.yaml"
    path.write_text(_ROOT.format(**values), encoding="utf-8")
    system, transformer = load_verilog_system(path, [str(tmp_path)])

    with pytest.raises(ValueError, match=message):
        transformer.transform(system)
    with pytest.raises(ValueError, match=message):  # same check as the RTL
        transformer.observe(system)


class TestVerilogTransformer:
    def test_transform_wraps_module_with_default_nettype_guards(self):
        assert_matches_fixture(INPUT_ROOT / "simple.yaml", EXPECTED_ROOT / "simple.sv")

    def test_logic_outputs_are_assigned_from_their_port_encoding(self):
        # x and m are stored in their logic port encodings: `assign x = state_x;`.
        assert_matches_fixture(
            INPUT_ROOT / "logic_outputs.yaml", EXPECTED_ROOT / "logic_outputs.sv"
        )

    def test_output_ports_driven_by_imported_outputs_are_assigned_once(self):
        # f and g are output ports bound to the child outputs: no second
        # declaration, one converted assignment each.
        assert_matches_fixture(
            INPUT_ROOT / "logic_output_import" / "parent.yaml",
            EXPECTED_ROOT / "logic_output_import" / "parent.sv",
            [str(INPUT_ROOT / "logic_output_import")],
        )

    def test_signed_multibit_logic_storage_is_declared_signed(self):
        # x is signed 8-bit logic: `logic signed [7:0] state_x`, so x < 0 is a
        # signed comparison (behavior checked by the opt-in Icarus test).
        assert_matches_fixture(
            INPUT_ROOT / "signed_logic_storage.yaml",
            EXPECTED_ROOT / "signed_logic_storage.sv",
        )

    def test_negative_constants_are_valid_signed_literals(self):
        # -1.5 in Q8.8 is written -16'sd384, not the invalid 16'sd-384.
        assert_matches_fixture(
            INPUT_ROOT / "negative_literals.yaml",
            EXPECTED_ROOT / "negative_literals.sv",
        )

    def test_fixed_point_products_and_quotients_keep_their_scale(self):
        # x * 0.5 is 16'((32'(state_x) * 32'(_VAL_0_5)) >>> 8): computed in
        # double width, shifted back by the fractional bits, cast to 16 bits.
        assert_matches_fixture(
            INPUT_ROOT / "fixed_point_arithmetic.yaml",
            EXPECTED_ROOT / "fixed_point_arithmetic.sv",
        )

    def test_numbers_driving_external_inputs_are_encoded_per_port(self):
        # 2.5 -> _VAL_2_5 (fixed), 1 -> 1'b1 (one bit), 3 -> 8'd3 (logic);
        # an empty connection and 0 drive 0.
        assert_matches_fixture(
            INPUT_ROOT / "external_numbers" / "root.yaml",
            EXPECTED_ROOT / "external_numbers" / "root.sv",
            [str(INPUT_ROOT / "external_numbers")],
        )
        result = read_fixture(EXPECTED_ROOT / "external_numbers" / "root.sv")
        for connection in (
            ".level(_VAL_2_5),",
            ".en(1'b1),",
            ".mode(8'd3),",
            ".spare(0),",
            ".zero(0),",
        ):
            assert connection in result

    def test_rules_read_renamed_input_ports(self):
        # Rules read input `a` through its renamed port `a_in`.
        assert_matches_fixture(
            INPUT_ROOT / "renamed_ports.yaml", EXPECTED_ROOT / "renamed_ports.sv"
        )

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

    @pytest.mark.parametrize(
        ("model", "golden"),
        [
            ("imports_externals/sensor.yaml", "imports_externals/sensor.sv"),
            (
                "blink_uart_boundary/blink_uart_tx_driver.yaml",
                "blink_uart_boundary/blink_uart_tx_driver.sv",
            ),
        ],
    )
    def test_imported_modules_match_their_goldens(self, model, golden):
        # Imported modules are emitted as their own .sv files in the closure.
        path = INPUT_ROOT / model
        assert_matches_fixture(path, EXPECTED_ROOT / golden, [str(path.parent)])

    def test_imported_module_is_connected_through_renamed_ports(self):
        # The child renames a -> a_in and y -> y_out; the instance must use them.
        assert_matches_fixture(
            INPUT_ROOT / "renamed_import" / "parent.yaml",
            EXPECTED_ROOT / "renamed_import" / "parent.sv",
            [str(INPUT_ROOT / "renamed_import")],
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

    def test_logic_vector_top_output_keeps_its_value(self):
        # leds is stored in its 6-bit port encoding: assigned directly, unshifted.
        assert_matches_fixture(
            INPUT_ROOT / "logic_vector.yaml", EXPECTED_ROOT / "logic_vector.sv"
        )

    def test_multiple_logic_vector_outputs_are_assigned_directly(self):
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
