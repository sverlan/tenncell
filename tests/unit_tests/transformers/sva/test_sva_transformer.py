"""Contract tests for SvaTransformer (Python API; the -t sva CLI comes later)."""

from pathlib import Path

import pytest

from nnc.cli_transform import (
    _collect_import_closure,
    _parse_verification_configs,
    _parse_verilog_configs,
)
from nnc.model.system import NncSystem
from nnc.transformers import SvaTransformer, VerilogTransformer
from nnc.verification.sva import SOURCES_DIR, SvaOptions
from nnc.verification.sva_stimulus import SvaStimulusSource

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "verification" / "sva"


def _load(path: Path, options: SvaOptions | None = None):
    cache: dict = {}
    import_paths = [str(path.parent)]
    system = NncSystem.from_yaml(
        str(path), import_paths=import_paths, _raw_data_cache=cache
    )
    closure = _collect_import_closure(system)
    verilog_configs = _parse_verilog_configs(closure, cache, import_paths)
    transformer = SvaTransformer(
        options or SvaOptions(),
        verilog_configs,
        _parse_verification_configs([system], cache),
    )
    return system, closure, verilog_configs, transformer


@pytest.mark.parametrize(
    "model", ["controller.yaml", "import_closure/parent.yaml", "external/root.yaml"]
)
def test_rtl_closure_is_exactly_the_verilog_output(model):
    system, closure, verilog_configs, transformer = _load(FIXTURES / model)
    verilog = VerilogTransformer(verilog_configs)

    files = transformer.generate(system).files
    stem = Path(system.source_path).stem
    sva_files = {f"{stem}_sva.sv", f"{stem}_sva_bind.sv"}
    rtl_files = {name: text for name, text in files.items() if name not in sva_files}

    assert rtl_files == {
        f"{Path(item.source_path).stem}.sv": verilog.transform(item) for item in closure
    }


def test_import_closure_has_one_file_per_module():
    system, *_, transformer = _load(FIXTURES / "import_closure" / "parent.yaml")

    assert sorted(transformer.generate(system).files) == [
        "child.sv",
        "parent.sv",
        "parent_sva.sv",
    ]


def test_checker_interface_raw_entries_and_bind_match_goldens():
    fixture = FIXTURES / "checker_interface"
    system, *_, transformer = _load(fixture / "root.yaml", SvaOptions(mode="both"))

    files = transformer.generate(system).files

    assert files["root_sva.sv"] == (fixture / "expected_checker.sv").read_text(
        encoding="utf-8"
    )
    assert files["root_sva_bind.sv"] == (fixture / "expected_bind.sv").read_text(
        encoding="utf-8"
    )


def test_imported_input_is_copied_for_row_alignment():
    fixture = FIXTURES / "imported_input" / "parent.yaml"
    system, *_, transformer = _load(fixture)

    checker = transformer.generate(system).files["parent_sva.sv"]

    assert "logic signed [15:0] sva_input_child0_a;" in checker
    assert "sva_input_child0_a <= 16'sd0;" in checker
    assert "sva_input_child0_a <= x;" in checker
    assert "(sva_input_child0_a == child0__y)" in checker


def test_monitors_match_golden():
    # Behavior is checked against native by the opt-in Icarus test
    # (tests/functional_tests/test_sva_monitors_icarus.py).
    fixture = FIXTURES / "monitors"
    system, *_, transformer = _load(fixture / "monitors.yaml")

    output = transformer.generate(system)

    checker = output.files["monitors_sva.sv"]
    assert checker == (fixture / "expected_monitors_sva.sv").read_text(encoding="utf-8")
    assert output.warnings == ()
    # Zero bounds (after: 0, within: [0, 0], then_always without after) have
    # dedicated code: no empty or reversed history vectors.
    assert "[-1:0]" not in checker
    assert "[0:1]" not in checker
    assert "sva_response_after_zero_fail_pending" not in checker
    assert "sva_response_within_zero_pending" not in checker
    assert "sva_always_after_zero_fail_age" not in checker


def test_testbench_matches_golden():
    # Behavior is checked against native by the opt-in simulation test
    # (tests/functional_tests/test_sva_simulation.py).
    fixture = FIXTURES / "monitors"
    cache: dict = {}
    import_paths = [str(fixture)]
    system = NncSystem.from_yaml(
        str(fixture / "monitors.yaml"), import_paths=import_paths, _raw_data_cache=cache
    )
    transformer = SvaTransformer(
        SvaOptions(),
        _parse_verilog_configs(_collect_import_closure(system), cache, import_paths),
        _parse_verification_configs([system], cache),
        SvaStimulusSource(inputs=fixture / "inputs.csv"),
    )

    files = transformer.generate(system).files

    assert files["monitors_tb.sv"] == (fixture / "expected_monitors_tb.sv").read_text(
        encoding="utf-8"
    )
    assert files["monitors_inputs.hex"].splitlines()[2:] == [
        "0100",
        "0200",
        "0500",
        "0000",
        "0300",
        "0000",
    ]


def test_concurrent_checker_matches_golden():
    # Every kind as one assert/cover property; strict end of run via strong
    # operators. Checked by slang (opt-in tests/functional_tests/test_sva_slang.py).
    fixture = FIXTURES / "monitors"
    system, *_, transformer = _load(
        fixture / "monitors.yaml", SvaOptions(style="concurrent")
    )

    output = transformer.generate(system)

    checker = output.files["monitors_sva.sv"]
    assert checker == (fixture / "expected_monitors_concurrent_sva.sv").read_text(
        encoding="utf-8"
    )
    assert output.warnings == ()
    assert "sva_report" not in checker
    assert "[-1:0]" not in checker


def test_concurrent_testbench_does_not_call_the_report_task():
    fixture = FIXTURES / "monitors"
    cache: dict = {}
    import_paths = [str(fixture)]
    system = NncSystem.from_yaml(
        str(fixture / "monitors.yaml"), import_paths=import_paths, _raw_data_cache=cache
    )
    transformer = SvaTransformer(
        SvaOptions(style="concurrent"),
        _parse_verilog_configs(_collect_import_closure(system), cache, import_paths),
        _parse_verification_configs([system], cache),
        SvaStimulusSource(inputs=fixture / "inputs.csv"),
    )

    testbench = transformer.generate(system).files["monitors_tb.sv"]

    assert "sva_report" not in testbench
    assert "$fatal" not in testbench
    assert "$finish;" in testbench


def test_weak_semantics_report_open_obligations_as_pending():
    fixture = FIXTURES / "monitors"
    system, *_, transformer = _load(fixture / "weak.yaml")

    checker = transformer.generate(system).files["weak_sva.sv"]

    assert '$display("SVA_RESULT open pending - -");' in checker
    assert '$display("SVA_OPEN open end");' in checker
    assert '$display("SVA_RESULT window_open pending - -");' in checker
    assert '$display("SVA_OPEN window_open end");' in checker
    assert "SVA_RESULT open fail" not in checker


def test_checker_without_from_step_or_windows_has_no_step_counter():
    system, *_, transformer = _load(FIXTURES / "controller.yaml")

    checker = transformer.generate(system).files["controller_sva.sv"]

    assert "sva_step" not in checker
    assert "[-1:0]" not in checker


def test_simulation_mode_omits_bind_file():
    system, *_, transformer = _load(FIXTURES / "controller.yaml")

    assert "controller_sva_bind.sv" not in transformer.generate(system).files


def test_modules_with_the_same_file_name_are_rejected():
    # drivers/a/controller.yaml and drivers/b/controller.yaml would both become
    # controller.sv; one module would be lost.
    system, *_, transformer = _load(FIXTURES / "stem_collision" / "root.yaml")

    with pytest.raises(ValueError) as error:
        transformer.generate(system)

    message = str(error.value)
    assert "would be written to the same RTL file" in message
    assert "controller.sv from " in message
    assert str(Path("drivers") / "a" / "controller.yaml") in message
    assert str(Path("drivers") / "b" / "controller.yaml") in message


def test_file_names_differing_only_by_case_are_rejected():
    # Controller.sv and controller.sv are one file on Windows and macOS; the
    # check is case-insensitive everywhere and keeps the original spellings.
    system, *_, transformer = _load(FIXTURES / "case_collision" / "root.yaml")

    with pytest.raises(ValueError) as error:
        transformer.generate(system)

    message = str(error.value)
    assert "would be written to the same RTL file" in message
    assert "Controller.sv from " in message
    assert "controller.sv from " in message


def test_sva_file_name_collision_is_rejected_case_insensitively():
    system, *_, transformer = _load(FIXTURES / "sva_file_collision" / "root.yaml")

    with pytest.raises(ValueError) as error:
        transformer.generate(system)

    assert str(error.value) == (
        "SVA-specific output file names collide with generated RTL: root_sva.sv"
    )


def test_externals_without_sources_give_a_warning(tmp_path):
    system, *_, transformer = _load(FIXTURES / "external" / "root.yaml")
    source = tmp_path / "uart.v"
    source.write_text("module uart; endmodule\n", encoding="utf-8")
    *_, with_source = _load(
        FIXTURES / "external" / "root.yaml", SvaOptions(sources=(source,))
    )

    assert transformer.generate(system).warnings == (
        "the RTL instantiates external modules (verilog.externals); pass their "
        "sources with --sva-source so simulators and formal tools can find them",
    )
    assert with_source.generate(system).warnings == ()


def test_write_puts_rtl_and_sources_in_the_output_directory(tmp_path):
    source = tmp_path / "ext" / "uart.v"
    source.parent.mkdir()
    source.write_text("module uart; endmodule\n", encoding="utf-8")
    system, *_, transformer = _load(
        FIXTURES / "external" / "root.yaml", SvaOptions(sources=(source,))
    )
    output = transformer.generate(system)
    out = tmp_path / "out"

    written = transformer.write(output, out)

    assert written == [
        out / "root.sv",
        out / "root_sva.sv",
        out / SOURCES_DIR / "uart.v",
    ]
    assert (out / "root.sv").read_text(encoding="utf-8") == output.files["root.sv"]
    assert (out / SOURCES_DIR / "uart.v").read_text(encoding="utf-8") == (
        "module uart; endmodule\n"
    )
