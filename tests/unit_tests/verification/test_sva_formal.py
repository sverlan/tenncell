"""Contract tests for SVA formal output: input assumptions, checker, .sby."""

from pathlib import Path

import pytest

from nnc.cli_transform import (
    _collect_import_closure,
    _parse_verification_configs,
    _parse_verilog_configs,
)
from nnc.model.system import NncSystem
from nnc.transformers import SvaTransformer, VerilogTransformer
from nnc.verification.config import InputEnvironment
from nnc.verification.generic_properties.native import VerificationError
from nnc.verification.sva import SvaOptions
from nnc.transformers.verilog.generation.observation import (
    INPUT_PORT,
    ObservedSignal,
    VerilogObservation,
)
from nnc.verification.sva_checker import _formal_block
from nnc.verification.sva_formal import input_assumptions

SVA = Path(__file__).resolve().parents[2] / "fixtures" / "verification" / "sva"
FORMAL = SVA / "formal"
ENCODING = SVA / "stimulus" / "encoding.yaml"


def _load(model: Path):
    cache: dict = {}
    import_paths = [str(model.parent)]
    system = NncSystem.from_yaml(
        str(model), import_paths=import_paths, _raw_data_cache=cache
    )
    configs = _parse_verilog_configs(
        _collect_import_closure(system), cache, import_paths
    )
    return system, cache, configs


def _observation():
    system, _, configs = _load(ENCODING)
    return VerilogTransformer(configs).observe(system)


def _generate(model: Path, options: SvaOptions):
    system, cache, configs = _load(model)
    transformer = SvaTransformer(
        options, configs, _parse_verification_configs([system], cache)
    )
    return transformer.generate(system)


def test_ranges_are_rounded_inward_in_the_port_encoding():
    # a: signed Q8.8 (-0.3 * 256 = -76.8 -> -76; 0.5 * 256 = 128);
    # b: unsigned 4-bit logic (1.5 -> 2, 9.9 -> 9).
    assumptions, warnings = input_assumptions(
        {"a": InputEnvironment((-0.3, 0.5)), "b": InputEnvironment((1.5, 9.9))},
        _observation(),
    )

    assert [(a.name, a.low, a.high) for a in assumptions] == [
        ("a", -76, 128),
        ("b", 2, 9),
    ]
    assert assumptions[0].literal(-76) == "-16'sd76"
    assert assumptions[1].literal(9) == "4'd9"
    assert warnings == ()


def _port(name: str, kind: str, width: int, signed: bool, frac_bits: int):
    return ObservedSignal(name, name, INPUT_PORT, kind, width, signed, frac_bits, True)


def _ports(*signals: ObservedSignal) -> VerilogObservation:
    return VerilogObservation(
        "m", "clk", "rst", True, {signal.name: signal for signal in signals}
    )


def test_signed_logic_and_unsigned_fixed_point_bounds():
    # s: signed 8-bit logic (-3.5 -> -3, 2.5 -> 2); f: unsigned 12-bit with
    # 8 fractional bits (0.3 * 256 = 76.8 -> 77; 1.5 * 256 = 384).
    assumptions, warnings = input_assumptions(
        {"s": InputEnvironment((-3.5, 2.5)), "f": InputEnvironment((0.3, 1.5))},
        _ports(_port("s", "logic", 8, True, 0), _port("f", "fixed", 12, False, 8)),
    )

    assert [(a.low, a.high) for a in assumptions] == [(-3, 2), (77, 384)]
    assert assumptions[0].literal(-3) == "-8'sd3"
    assert assumptions[1].literal(77) == "12'd77"
    assert warnings == ()


def test_huge_finite_ranges_are_clipped_not_overflowed():
    assumptions, warnings = input_assumptions(
        {"f": InputEnvironment((-1e308, 1e308))},
        _ports(_port("f", "fixed", 16, True, 8)),
    )

    assert [(a.low, a.high) for a in assumptions] == [(-32768, 32767)]
    assert len(warnings) == 1 and "is clipped" in warnings[0]


@pytest.mark.parametrize(
    ("active_high", "assume", "guard", "enable"),
    [
        (True, "assume (rst == sva_formal_reset);", "if (!(rst)) begin", ".en(!(rst))"),
        (
            False,
            "assume (!rst == sva_formal_reset);",
            "if (!(!rst)) begin",
            ".en(!(!rst))",
        ),
    ],
)
def test_reset_scheme_follows_the_reset_polarity(active_high, assume, guard, enable):
    # An active-low reset cannot be configured in YAML yet; the formal block
    # supports both polarities.
    observation = VerilogObservation("m", "clk", "rst", active_high, {})
    used: set[str] = set()

    def fresh(base: str) -> str:
        used.add(base)
        return base

    lines = _formal_block(
        observation,
        [("p", "assert", "p_bad"), ("q", "live", "q_ok"), ("r", "live", "r_ok")],
        [],
        (),
        fresh,
    )

    assert f"always @(*) {assume}" in lines
    assert f"    {guard}" in lines
    assert "        sva_p_check: assert (!p_bad);" in lines
    # Liveness obligations start when the reset is released.
    assert f"m_sva_live sva_liveness (.a((q_ok) && (r_ok)), {enable});" in lines


def test_ranges_wider_than_the_port_are_clipped_with_a_warning():
    # d: unsigned 12-bit fixed point (0 .. 4095/256); b: 4-bit logic (0 .. 15).
    assumptions, warnings = input_assumptions(
        {"d": InputEnvironment((-1, 100)), "b": InputEnvironment((3, 20))},
        _observation(),
    )

    assert [(a.low, a.high) for a in assumptions] == [(0, 4095), (3, 15)]
    assert warnings == (
        "verification.environment.d.range [-1, 100] is clipped to the values port "
        "'d' can hold",
        "verification.environment.b.range [3, 20] is clipped to the values port "
        "'b' can hold",
    )


@pytest.mark.parametrize(
    ("environment", "message"),
    [
        (
            {"b": InputEnvironment((20, 30))},
            r"\[20, 30\] has no value representable on port 'b'",
        ),
        (
            {"b": InputEnvironment((0.2, 0.8))},
            r"\[0\.2, 0\.8\] has no value representable",
        ),
        (
            {"a": InputEnvironment((0, float("inf")))},
            "must be finite for formal checks",
        ),
    ],
)
def test_ranges_without_a_port_value_are_rejected(environment, message):
    with pytest.raises(VerificationError, match=message):
        input_assumptions(environment, _observation())


def test_formal_checker_and_sby_match_goldens():
    output = _generate(FORMAL / "follow.yaml", SvaOptions(mode="formal", depth=12))

    assert output.files["follow_sva.sv"] == (
        FORMAL / "expected_follow_sva.sv"
    ).read_text(encoding="utf-8")
    assert output.files["follow.sby"] == (FORMAL / "expected_follow.sby").read_text(
        encoding="utf-8"
    )
    assert sorted(output.files) == [
        "follow.sby",
        "follow.sv",
        "follow_sva.sv",
        "follow_sva_bind.sv",
    ]


def test_monitor_counters_get_invariants_for_induction():
    # The step counter saturates at 5 (from_step 3 + window 1, plus one); the
    # then_always age counter of `stays` stops at 2 and is 0 until armed.
    checker = _generate(FORMAL / "toggle.yaml", SvaOptions(mode="formal")).files[
        "toggle_sva.sv"
    ]

    assert "        sva_step_invariant: assert ((sva_step <= 3'd5));" in checker
    assert (
        "        sva_stays_age_invariant: assert ((sva_stays_age <= 2'd2) && "
        "(sva_stays_armed || sva_stays_age == 2'd0));"
    ) in checker


@pytest.mark.parametrize("mode", ["formal", "both"])
def test_unbounded_eventually_gets_a_liveness_check_and_live_task(mode):
    output = _generate(FORMAL / "liveness.yaml", SvaOptions(mode=mode, depth=4))
    checker = output.files["liveness_sva.sv"]
    sby = output.files["liveness.sby"]

    assert output.warnings == ()
    # Satisfied on an earlier row or this one; from_step gates the hit.
    assert (
        "assign sva_late_zero_hit_now = (sva_step >= 3'd5) && sva_late_zero_cond;"
        in checker
    )
    # The flag is monitor state, outside the simulation-only recorder.
    assert "sva_late_zero_seen <= 1'b1;" in checker.split("`ifndef FORMAL")[1]
    # One $live cell for all liveness properties (suprove checks only the
    # first one of a model): the conjunction of the sticky flags.
    assert (
        "// liveness: reaches_one, late_zero, reaches_two, input_reaches_max" in checker
    )
    assert (
        "formal_liveness_sva_live sva_liveness (.a("
        "(sva_reaches_one_seen || sva_reaches_one_hit_now) && "
        "(sva_late_zero_seen || sva_late_zero_hit_now) && "
        "(sva_reaches_two_seen || sva_reaches_two_hit_now) && "
        "(sva_input_reaches_max_seen || sva_input_reaches_max_hit_now)"
        "), .en(!(rst)));"
    ) in checker
    assert checker.count("formal_liveness_sva_live ") == 1
    assert "sva_late_zero_check" not in checker
    assert "sva_never_one_check: assert (!sva_never_one_failed_now);" in checker
    assert output.files["liveness_sva_live.v"].splitlines()[3:6] == [
        "module formal_liveness_sva_live (input wire a, input wire en);",
        "    \\$live live (.A(a), .EN(en));",
        "endmodule",
    ]
    for line in [
        "live",
        "live: mode live",
        "~live: depth 6",
        "live: aiger suprove",
        "read_verilog -formal -icells liveness_sva_live.v",
        "live: chformal -assert -remove",
    ]:
        assert line in sby.splitlines(), line
    assert sby.rstrip().endswith("liveness_sva_live.v")


def test_without_unbounded_eventually_there_is_no_live_task(tmp_path):
    output = _generate(FORMAL / "toggle.yaml", SvaOptions(mode="formal"))

    assert "toggle_sva_live.v" not in output.files
    assert "toggle_sva_live.v" in output.obsolete
    assert "live" not in output.files["toggle.sby"].splitlines()
    assert "_live " not in output.files["toggle_sva.sv"]


def test_simulation_mode_has_no_liveness_helper():
    output = _generate(FORMAL / "liveness.yaml", SvaOptions())

    assert "liveness_sva_live.v" not in output.files
    assert "formal_liveness_sva_live" not in output.files["liveness_sva.sv"]


def test_liveness_helper_module_name_must_not_be_an_rtl_module(tmp_path):
    # The imported module is named like the root's liveness helper.
    child = tmp_path / "child.yaml"
    child.write_text(
        "module:\n  name: top_sva_live\ncells:\n  - id: 1\n    contents:\n"
        "      - y = 0\n    output: [y]\nrules:\n  - y + 1 -> y\n"
        "verilog:\n  real_encoding: {kind: fixed_point, signed: true, width: 16, "
        "frac_bits: 8}\n",
        encoding="utf-8",
    )
    root = tmp_path / "top.yaml"
    root.write_text(
        "module:\n  name: top\nimports:\n  - module: child.yaml\n    as: c\n"
        "cells:\n  - id: 1\n    contents:\n      - x = 0\n    output: [x]\n"
        "rules:\n  - x + 1 -> x\n"
        "verilog:\n  real_encoding: {kind: fixed_point, signed: true, width: 16, "
        "frac_bits: 8}\n"
        "verification:\n  properties:\n    - id: p\n      eventually: x == 3\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="'top_sva_live' is already a module"):
        _generate(root, SvaOptions(mode="formal"))


def test_sby_lists_copied_sources_by_name(tmp_path):
    source = tmp_path / "uart.v"
    source.write_text("module uart; endmodule\n", encoding="utf-8")

    sby = _generate(
        SVA / "external" / "root.yaml", SvaOptions(mode="formal", sources=(source,))
    ).files["root.sby"]

    assert "read_slang -D FORMAL root.sv root_sva.sv root_sva_bind.sv uart.v" in sby
    assert sby.rstrip().endswith("sva_sources/uart.v")


def test_file_names_with_whitespace_are_rejected_for_formal_only(tmp_path):
    source = tmp_path / "uart model.sv"
    source.write_text("module uart; endmodule\n", encoding="utf-8")
    model = SVA / "external" / "root.yaml"

    with pytest.raises(ValueError, match="without whitespace.*: uart model.sv; rename"):
        _generate(model, SvaOptions(mode="formal", sources=(source,)))
    # Simulation does not list the files: the copied source is fine.
    assert "root_sva.sv" in _generate(model, SvaOptions(sources=(source,))).files


def test_model_and_import_file_names_with_whitespace_are_rejected(tmp_path):
    (tmp_path / "my child.yaml").write_text(
        "module:\n  name: child\n"
        "cells:\n  - id: 1\n    contents:\n      - a = 0, y = 0\n    input: [a]\n"
        "    output: [y]\nrules:\n  - a -> y\n"
        "verilog:\n  real_encoding: {kind: fixed_point, signed: true, width: 16, "
        "frac_bits: 8}\n",
        encoding="utf-8",
    )
    root = tmp_path / "my root.yaml"
    root.write_text(
        "module:\n  name: root\n"
        "imports:\n  - module: my child.yaml\n    as: c0\n    connections: {a: x}\n"
        "cells:\n  - id: 1\n    contents:\n      - x = 0\n    output: [x]\n"
        "rules:\n  - x + 1 -> x\n"
        "verilog:\n  real_encoding: {kind: fixed_point, signed: true, width: 16, "
        "frac_bits: 8}\n"
        "verification:\n  properties:\n    - id: p\n      always: x >= 0\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="without whitespace.*: my child.sv, my root.sv, my root_sva.sv;",
    ):
        _generate(root, SvaOptions(mode="formal"))


def test_source_named_like_a_generated_file_is_rejected(tmp_path):
    source = tmp_path / "root_sva.sv"
    source.write_text("module x; endmodule\n", encoding="utf-8")

    with pytest.raises(
        ValueError, match="have the names of generated files.*root_sva.sv"
    ):
        _generate(
            SVA / "external" / "root.yaml", SvaOptions(mode="formal", sources=(source,))
        )
