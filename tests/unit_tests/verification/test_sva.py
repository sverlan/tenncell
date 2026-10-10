"""Contract tests for SVA options, property selection and source handling."""

from pathlib import Path

import pytest

from nnc.cli_transform import (
    _collect_import_closure,
    _parse_verification_configs,
    _parse_verilog_configs,
)
from nnc.inputs.yaml.errors import YamlLocatedError
from nnc.model.system import NncSystem
from nnc.transformers import SvaTransformer
from nnc.verification.sva import (
    SOURCES_DIR,
    SvaOptions,
    SvaOptionsError,
    copy_sources,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "verification" / "sva"
CONTROLLER = FIXTURES / "controller.yaml"


def _generate(path: Path, options: SvaOptions | None = None):
    cache: dict = {}
    system = NncSystem.from_yaml(
        str(path), import_paths=[str(path.parent)], _raw_data_cache=cache
    )
    transformer = SvaTransformer(
        options or SvaOptions(),
        _parse_verilog_configs(
            _collect_import_closure(system), cache, [str(path.parent)]
        ),
        _parse_verification_configs([system], cache),
    )
    return transformer.generate(system), transformer


# Base model for the small error tables below (inline by design).
_BASE = (
    "cells:\n  - id: 1\n    contents:\n      - x = 0\n    output: [x]\n"
    "rules:\n  - x + 1 -> x\n"
    "verilog:\n  real_encoding: {kind: fixed_point, signed: true, width: 16, "
    "frac_bits: 8}\n"
)


def _model(tmp_path: Path, verification: str) -> Path:
    path = tmp_path / "model.yaml"
    path.write_text(_BASE + verification, encoding="utf-8")
    return path


# --- options ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"mode": "emulation"}, "SVA mode must be one of"),
        ({"style": "fancy"}, "SVA style must be one of"),
        ({"depth": 10}, "depth applies to formal checks only"),
        ({"mode": "formal", "depth": 0}, "depth must be a positive integer"),
        ({"style": "concurrent", "mode": "formal"}, "concurrent style is available"),
        ({"style": "concurrent", "mode": "both"}, "concurrent style is available"),
        ({"max_bound": 0}, "maximum bound must be a positive integer"),
        ({"mode": "formal", "depth": 1.5}, "depth must be an integer"),
        ({"mode": "formal", "depth": True}, "depth must be an integer"),
        ({"max_bound": 2.5}, "maximum bound must be an integer"),
    ],
)
def test_invalid_options(fields, message):
    with pytest.raises(SvaOptionsError, match=message):
        SvaOptions(**fields)


def test_option_defaults_apply_only_when_not_given():
    assert SvaOptions().effective_max_bound == 1024
    assert SvaOptions(mode="formal").effective_depth == 20
    assert SvaOptions(mode="both", depth=7).effective_depth == 7
    assert SvaOptions(max_bound=5).effective_max_bound == 5
    assert SvaOptions().simulation and not SvaOptions().formal
    assert SvaOptions(mode="both").simulation and SvaOptions(mode="both").formal


# --- selection ----------------------------------------------------------------


def test_selection_in_simulation_mode():
    output, _ = _generate(CONTROLLER)
    selection = output.selection

    assert [p.bound.property.id for p in selection.properties] == [
        "level_bounded",
        "request_served",
        "reaches_busy",
    ]
    # Signals the conditions read, trigger first, as RTL signals.
    served = selection.properties[1]
    assert {name: s.expression for name, s in served.signals.items()} == {
        "req": "req",
        "mode": "state_mode",
        "ack": "state_ack",
    }
    (raw,) = selection.raw
    assert raw.bound.entry.id == "level_limit"
    assert list(raw.signals) == ["mode", "level"]
    assert output.warnings == (
        "generic verification properties skipped for SVA: "
        "uses_abs (calls abs; SVA conditions are RTL expressions without function "
        "calls); level_times_req (its condition cannot be expressed in RTL (Verilog "
        "export does not support variable-by-variable multiplication)); "
        "slow_response (after 2000 is above the SVA bound limit 1024)",
    )


@pytest.mark.parametrize("mode", ["formal", "both"])
def test_unbounded_eventually_is_selected_in_formal_modes(mode):
    # Checked as liveness (the live task), with no warning about it.
    output, _ = _generate(CONTROLLER, SvaOptions(mode=mode))

    assert "reaches_busy" in [p.bound.property.id for p in output.selection.properties]
    assert not any("reaches_busy" in warning for warning in output.warnings)


def test_max_bound_option_admits_larger_bounds():
    output, _ = _generate(CONTROLLER, SvaOptions(max_bound=2000))

    assert "slow_response" in [p.bound.property.id for p in output.selection.properties]


@pytest.mark.parametrize(
    ("verification", "options", "message"),
    [
        (
            "verification:\n  properties:\n    - id: p\n      always: abs(x) < 9\n"
            "      targets: [sva]\n",
            SvaOptions(),
            r"model\.yaml:14: Verification property 'p': targets sva, but calls abs",
        ),
        (
            "verification:\n  properties:\n    - id: q\n      always: x >= 0\n"
            "  backends:\n    sva:\n      raw:\n        - id: q\n"
            "          code: assert (1);\n",
            SvaOptions(),
            r"model\.yaml:12: Verification property 'q': ID is also used by an sva raw",
        ),
        (
            "verification:\n  trace_semantics: weak\n  properties:\n    - id: p\n"
            "      always: x >= 0\n",
            SvaOptions(style="concurrent"),
            r"model\.yaml:11: concurrent SVA style does not support trace_semantics: weak",
        ),
        (
            "verification:\n  backends:\n    sva:\n      trace_semantics: weak\n"
            "  properties:\n    - id: p\n      always: x >= 0\n",
            SvaOptions(style="concurrent"),
            r"model\.yaml:13: concurrent SVA style does not support",
        ),
    ],
)
def test_selection_errors(tmp_path, verification, options, message):
    with pytest.raises(YamlLocatedError, match=message):
        _generate(_model(tmp_path, verification), options)


@pytest.mark.parametrize(
    ("property_", "reason"),
    [
        (
            "always: x >= 0\n      from_step: 5",
            "from_step 5 is above the SVA bound limit 4",
        ),
        ("eventually: x > 1\n      within: [1, 5]", "within upper bound 5 is above"),
        ("eventually: x > 1\n      within: [0, 4]\n      from_step: 5", "from_step 5"),
        (
            "when: x > 0\n      then: x > 1\n      within: [0, 5]",
            "within upper bound 5",
        ),
        ("when: x > 0\n      then_always: x > 1\n      after: 5", "after 5 is above"),
        ("never: x < 0\n      from_step: 5", "from_step 5 is above"),
        ("cover: x > 3\n      from_step: 5", "from_step 5 is above"),
    ],
)
def test_every_bound_of_every_kind_is_limited(tmp_path, property_, reason):
    path = _model(
        tmp_path,
        "verification:\n  properties:\n    - id: ok\n      always: x >= 0\n"
        "    - id: p\n      " + property_ + "\n",
    )

    output, _ = _generate(path, SvaOptions(max_bound=4))

    assert [p.bound.property.id for p in output.selection.properties] == ["ok"]
    assert reason in output.warnings[0]


def test_bounds_at_the_limit_are_accepted(tmp_path):
    path = _model(
        tmp_path,
        "verification:\n  properties:\n    - id: p\n      when: x > 0\n"
        "      then: x > 1\n      within: [0, 4]\n      from_step: 4\n",
    )

    output, _ = _generate(path, SvaOptions(max_bound=4))

    assert [p.bound.property.id for p in output.selection.properties] == ["p"]
    assert output.warnings == ()


def test_generic_property_reading_a_converted_import_input_is_skipped():
    output, _ = _generate(FIXTURES / "converted_import" / "property.yaml")

    assert [p.bound.property.id for p in output.selection.properties] == ["led_low"]
    assert output.warnings == (
        "generic verification properties skipped for SVA: child_input_small (reads "
        "'child0.sig', which is not a plain signal in the generated RTL)",
    )


def test_aliases_read_their_target_signal(tmp_path):
    path = _model(
        tmp_path,
        "aliases:\n  count: x\n"
        "verification:\n  properties:\n    - id: p\n      always: count >= 0\n",
    )

    output, _ = _generate(path)

    (prop,) = output.selection.properties
    assert {name: s.expression for name, s in prop.signals.items()} == {"x": "state_x"}


def test_targeted_unbounded_eventually_is_accepted_in_formal_mode(tmp_path):
    path = _model(
        tmp_path,
        "verification:\n  properties:\n    - id: p\n      eventually: x > 3\n"
        "      targets: [sva]\n",
    )

    output, _ = _generate(path, SvaOptions(mode="formal"))

    (prop,) = output.selection.properties
    assert prop.bound.property.id == "p"
    assert output.warnings == ()


def test_native_only_property_may_share_an_id_with_a_raw_entry(tmp_path):
    path = _model(
        tmp_path,
        "verification:\n  properties:\n    - id: q\n      always: x >= 0\n"
        "      targets: [native]\n  backends:\n    sva:\n      raw:\n"
        "        - id: q\n          code: assert (1);\n",
    )

    output, _ = _generate(path)

    assert output.selection.properties == ()
    assert [r.bound.entry.id for r in output.selection.raw] == ["q"]


def test_concurrent_style_with_strict_semantics_gives_assertions(tmp_path):
    path = _model(
        tmp_path, "verification:\n  properties:\n    - id: p\n      always: x >= 0\n"
    )

    output, _ = _generate(path, SvaOptions(style="concurrent"))

    checker = output.files["model_sva.sv"]
    assert "sva_p: assert property (@(posedge clk) disable iff (rst)" in checker
    assert "sva_report" not in checker


def test_raw_placeholder_must_name_a_plain_rtl_signal():
    with pytest.raises(
        YamlLocatedError,
        match=r"Raw entry 'child_input': placeholder '\$\{child0\.sig\}' names "
        r"'child0\.sig', which is not a plain signal in the generated RTL",
    ):
        _generate(FIXTURES / "converted_import" / "root.yaml")


@pytest.mark.parametrize(
    "verification",
    [
        "verification:\n  properties:\n    - id: p\n      always: x >= 0\n"
        "      targets: [native]\n",
        "verification:\n  properties:\n    - id: p\n      always: abs(x) >= 0\n",
    ],
)
def test_nothing_to_emit_is_an_error(tmp_path, verification):
    with pytest.raises(ValueError, match="No SVA verification entries found"):
        _generate(_model(tmp_path, verification))


@pytest.mark.parametrize(
    ("port", "kind", "width", "condition"),
    [
        ("sva_report", "fixed", 16, "u >= 0"),  # the report task
        ("sva_replay_check", "fixed", 16, "u >= 0"),  # the replay check task
        ("_VAL_2_0", "fixed", 16, "u >= 2"),  # the literal parameter of 2.0
        # u >= x converts the logic u to fixed point with this helper ...
        ("conv_logic_8_to_sfixed_16_8", "logic", 8, "u >= x"),
        # ... and the one-bit helper reads a literal 1.0 it creates itself.
        ("_VAL_1_0", "logic", 1, "u >= x"),
    ],
)
def test_checker_port_named_like_a_checker_declaration_is_an_error(
    tmp_path, port, kind, width, condition
):
    path = tmp_path / "model.yaml"
    path.write_text(
        "cells:\n  - id: 1\n    contents:\n      - u = 0, x = 0\n    input: [u]\n"
        "rules:\n  - x -> x\n"
        "verilog:\n  real_encoding: {kind: fixed_point, signed: true, width: 16, "
        f"frac_bits: 8}}\n  ports:\n    u: {{direction: input, kind: {kind}, "
        f"width: {width}, signed: {str(kind == 'fixed').lower()}, rename: {port}}}\n"
        f"verification:\n  properties:\n    - id: p\n      always: {condition}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=f"names the checker declares itself: {port};"):
        _generate(path)


@pytest.mark.parametrize(("after", "warned"), [(65519, False), (65520, True)])
def test_monitor_state_above_65536_bits_gives_a_warning(tmp_path, after, warned):
    # after n: n pending bits; then_always after 5: armed + 3-bit age;
    # eventually: seen; cover: covered; eventually within [0, 535]: seen + the
    # shared 10-bit step counter (it stops at 536). Total: n + 17.
    path = _model(
        tmp_path,
        "verification:\n  properties:\n"
        f"    - id: a\n      when: x > 0\n      then: x > 1\n      after: {after}\n"
        "    - id: b\n      when: x > 0\n      then_always: x > 1\n      after: 5\n"
        "    - id: c\n      eventually: x > 3\n"
        "    - id: d\n      cover: x > 3\n"
        "    - id: e\n      eventually: x > 3\n      within: [0, 535]\n",
    )

    output, _ = _generate(path, SvaOptions(max_bound=after))

    expected = (
        f"the SVA monitors keep {after + 17:,} bits of state (more than 65,536), "
        "so simulation and formal checks may be slow; lower the "
        "after/within/from_step bounds or --sva-max-bound"
    )
    assert (expected in output.warnings) is warned
    assert not any("bits of state" in w for w in output.warnings) or warned


def test_model_without_verification_section_is_an_error(tmp_path):
    with pytest.raises(ValueError, match="no verification section"):
        _generate(_model(tmp_path, ""))


# --- external sources ---------------------------------------------------------


def _source(tmp_path: Path, relative: str, text: str = "module m; endmodule\n") -> Path:
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_sources_are_copied_and_overwrite_but_do_not_clean(tmp_path):
    spaced = _source(tmp_path, "my sources/uart tx.v", "module uart_tx; endmodule\n")
    out = tmp_path / "out"
    stale = _source(out, f"{SOURCES_DIR}/old.v")
    _source(out, f"{SOURCES_DIR}/uart tx.v", "// previous version\n")

    copied = copy_sources((spaced,), out)

    assert copied == (out / SOURCES_DIR / "uart tx.v",)
    assert copied[0].read_text(encoding="utf-8") == "module uart_tx; endmodule\n"
    assert stale.is_file()  # not a clean mirror: earlier files stay


@pytest.mark.parametrize(
    ("relatives", "message"),
    [
        (["a/uart.v", "b/uart.v"], "have the same file name 'uart.v'"),
        # One file on Windows and macOS: compared ignoring case.
        (
            ["a/UART.v", "b/uart.v"],
            "have the same file name 'uart.v' \\(compared ignoring case\\)",
        ),
        (["missing.v"], "SVA source files not found"),
    ],
)
def test_bad_sources_are_rejected_before_anything_is_written(
    tmp_path, relatives, message
):
    sources = tuple(
        _source(tmp_path, r) if r != "missing.v" else tmp_path / r for r in relatives
    )
    out = tmp_path / "out"
    output, transformer = _generate(CONTROLLER, SvaOptions(sources=sources))

    with pytest.raises(SvaOptionsError, match=message):
        transformer.write(output, out)

    assert not out.exists()
