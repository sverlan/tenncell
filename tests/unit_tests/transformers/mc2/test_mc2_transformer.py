"""Contract tests for the MC2 verification transformer (raw entries and generic
properties)."""

from pathlib import Path

import pytest

from nnc import NncSystem
from nnc.cli_transform import _parse_verification_configs, _parse_webots_csv_configs
from nnc.inputs.yaml.errors import YamlLocatedError
from nnc.transformers import Mc2Transformer
from nnc.verification.mc2 import render_literal

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"
MC2 = FIXTURES / "transformers" / "mc2"
SUFFIXES = (".mc2.pltl", ".mc2.ids", ".mc2.columns")


def _transformer_for(path: Path) -> tuple[Mc2Transformer, NncSystem]:
    raw_cache: dict = {}
    system = NncSystem.from_yaml(str(path), _raw_data_cache=raw_cache)
    transformer = Mc2Transformer()
    transformer.set_verification_configs(
        _parse_verification_configs([system], raw_cache)
    )
    return transformer, system


def _expected(stem: str) -> dict[str, str]:
    return {
        suffix: (MC2 / "expected" / f"{stem}{suffix}").read_text(encoding="utf-8")
        for suffix in SUFFIXES
    }


@pytest.mark.parametrize(
    ("path", "stem"),
    [
        (
            FIXTURES / "verification" / "input" / "fsm_counter_mc2.yaml",
            "fsm_counter_mc2",
        ),
        (MC2 / "input" / "imported_mc2.yaml", "imported_mc2"),
        (MC2 / "input" / "generic_mc2.yaml", "generic_mc2"),
    ],
)
def test_emits_golden_mc2_files(path, stem):
    transformer, system = _transformer_for(path)

    files = transformer.transform_files(system)

    assert files == _expected(stem)
    assert transformer.transform(system) == files[".mc2.pltl"]
    assert transformer.get_file_extension() == ".mc2.pltl"


def test_generic_properties_follow_raw_entries():
    transformer, system = _transformer_for(
        FIXTURES / "verification" / "input" / "fsm_counter_mc2.yaml"
    )
    files = transformer.transform_files(system)

    assert files[".mc2.ids"].splitlines()[-1] == "bounded"
    assert transformer.warnings == [
        "MC2 trace columns are not root outputs, so nnc-sim traces will not "
        "contain them: ctrl_state",
    ]


def test_warns_only_about_columns_for_properties_targeting_other_backends():
    transformer, system = _transformer_for(MC2 / "input" / "imported_mc2.yaml")
    transformer.transform_files(system)

    # Imported IO and root inputs cannot appear in nnc-sim output traces.
    assert transformer.warnings == [
        "MC2 trace columns are not root outputs, so nnc-sim traces will not "
        "contain them: sensor0__level, sample"
    ]


def _model(tmp_path: Path, verification: str) -> Path:
    path = tmp_path / "model.yaml"
    path.write_text(
        "cells:\n  - id: 1\n    contents:\n      - x = 0\n    output: [x]\n"
        "rules:\n  - x + 1 -> x\n" + verification,
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize(
    "verification",
    [
        "",
        "verification:\n  trace_semantics: weak\n",
        "verification:\n  backends:\n    mc2:\n      trace_semantics: weak\n",
    ],
)
def test_requires_something_to_emit(tmp_path, verification):
    transformer, system = _transformer_for(_model(tmp_path, verification))

    with pytest.raises(ValueError, match=r"No MC2 verification entries found"):
        transformer.transform_files(system)


@pytest.mark.parametrize(
    ("properties", "warnings"),
    [
        # Only for native: not used by MC2, silently.
        ("    - id: a\n      always: x >= 0\n      targets: [native]\n", []),
        # Untargeted with a function call: skipped with a warning.
        (
            "    - id: a\n      always: abs(x) >= 0\n",
            [
                "generic verification properties skipped for MC2: a (calls abs; "
                "MC2 queries cannot call functions)"
            ],
        ),
    ],
)
def test_nothing_to_emit_after_filtering(tmp_path, properties, warnings):
    path = _model(tmp_path, "verification:\n  properties:\n" + properties)
    transformer, system = _transformer_for(path)

    with pytest.raises(ValueError, match=r"No MC2 verification entries found"):
        transformer.transform_files(system)
    assert transformer.warnings == warnings


def test_generic_properties_alone_are_emitted(tmp_path):
    path = _model(
        tmp_path,
        "verification:\n  properties:\n    - id: a\n      always: x >= 0\n",
    )
    transformer, system = _transformer_for(path)

    files = transformer.transform_files(system)

    assert files == {
        ".mc2.pltl": "P=?[G(([x] >= 0))]\n",
        ".mc2.ids": "a\n",
        ".mc2.columns": "x\n",
    }
    assert transformer.warnings == []


@pytest.mark.parametrize(
    ("properties", "message"),
    [
        (
            "    - id: a\n      always: abs(x) >= 0\n      targets: [native, mc2]\n",
            r"model\.yaml:12: Verification property 'a': targets mc2, but calls abs; "
            r"MC2 queries cannot call functions",
        ),
        (
            "    - id: q\n      always: x >= 0\n",
            r"model\.yaml:10: Verification property 'q': ID is also used by an mc2 "
            r"raw entry",
        ),
    ],
)
def test_generic_property_errors(tmp_path, properties, message):
    path = _model(
        tmp_path,
        "verification:\n  properties:\n" + properties + "  backends:\n    mc2:\n"
        '      raw:\n        - id: q\n          code: "P=?[ F([${x}] > 1) ]"\n',
    )
    transformer, system = _transformer_for(path)

    with pytest.raises(YamlLocatedError, match=message):
        transformer.transform_files(system)


@pytest.mark.parametrize(
    ("where", "expected"),
    [
        ("  trace_semantics: weak\n", True),
        ("  backends:\n    mc2:\n      trace_semantics: weak\n", True),
        (
            "  trace_semantics: weak\n  backends:\n    mc2:\n"
            "      trace_semantics: strict\n",
            False,
        ),
    ],
)
def test_weak_semantics_warnings(tmp_path, where, expected):
    path = _model(
        tmp_path,
        "verification:\n" + where + "  properties:\n"
        "    - id: soon\n      eventually: x > 1\n      within: [0, 2]\n"
        "    - id: later\n      eventually: x > 1\n"
        "    - id: safe\n      always: x >= 0\n",
    )
    transformer, system = _transformer_for(path)

    transformer.transform_files(system)

    weak_warnings = [
        "trace_semantics weak: MC2 counts obligations still open at the end of the "
        "trace as satisfied (native reports pending): soon",
        "trace_semantics weak: MC2 checks unbounded 'eventually' strictly, so an "
        "unmet condition gives 0 (native reports pending): later",
    ]
    assert transformer.warnings == (weak_warnings if expected else [])


@pytest.mark.parametrize(
    ("property_", "approximated"),
    [
        ("eventually: x > 1\n      within: [0, 0]\n", False),
        ("eventually: x > 1\n      within: [0, 0]\n      from_step: 2\n", True),
        ("when: x > 0\n      then: x > 1\n      after: 0\n", False),
        ("when: x > 0\n      then: x > 1\n      after: 1\n", True),
        ("when: x > 0\n      then: x > 1\n      within: [0, 0]\n", False),
        ("when: x > 0\n      then: x > 1\n      within: [0, 1]\n", True),
        ("when: x > 0\n      then_always: x > 1\n      after: 2\n", False),
    ],
)
def test_weak_warning_only_when_an_obligation_can_stay_open(
    tmp_path, property_, approximated
):
    # With a zero bound (and no from_step for `eventually`), nothing can stay
    # open at the end, so the weak MC2 query is exact.
    path = _model(
        tmp_path,
        "verification:\n  trace_semantics: weak\n  properties:\n"
        "    - id: p\n      " + property_,
    )
    transformer, system = _transformer_for(path)

    transformer.transform_files(system)

    assert (
        any("trace_semantics weak" in w for w in transformer.warnings) == approximated
    )


def test_generic_columns_follow_raw_columns_without_duplicates():
    transformer, system = _transformer_for(MC2 / "input" / "two_columns.yaml")

    assert transformer.transform_files(system)[".mc2.columns"] == "x\ny\n"


@pytest.mark.parametrize(
    ("code", "message"),
    [
        (
            "|\n            P=?[ F([${x}] > 1)\n            ]\n",
            r"model\.yaml:13: Raw entry 'q': MC2 query must be a single line",
        ),
        ('"  "\n', r"model\.yaml:13: Raw entry 'q': MC2 query must not be empty"),
    ],
)
def test_rejects_entries_that_are_not_one_query(tmp_path, code, message):
    path = _model(
        tmp_path,
        "verification:\n  backends:\n    mc2:\n      raw:\n"
        "        - id: q\n          code: " + code,
    )
    transformer, system = _transformer_for(path)

    with pytest.raises(YamlLocatedError, match=message):
        transformer.transform_files(system)


def _transformer_with_webots_log(path: Path) -> tuple[Mc2Transformer, NncSystem]:
    raw_cache: dict = {}
    system = NncSystem.from_yaml(str(path), _raw_data_cache=raw_cache)
    transformer = Mc2Transformer()
    transformer.set_verification_configs(
        _parse_verification_configs([system], raw_cache)
    )
    transformer.set_webots_csv_configs(_parse_webots_csv_configs([system], raw_cache))
    return transformer, system


def test_columns_logged_by_webots_csv_need_no_warning():
    transformer, system = _transformer_with_webots_log(
        MC2 / "input" / "webots_logged.yaml"
    )
    transformer.transform_files(system)

    # `s` (an input) and `w` (internal) are not outputs, but the Webots log records them.
    assert transformer.warnings == []


def test_warns_when_webots_log_cannot_serve_mc2():
    transformer, system = _transformer_with_webots_log(
        MC2 / "input" / "webots_log_unreadable.yaml"
    )
    transformer.transform_files(system)

    assert transformer.warnings == [
        "MC2 trace columns are neither root outputs (nnc-sim traces) nor listed in "
        "webots.csv.variables (Webots CSV log): s",
        "webots.csv.include_step is false, but MC2 reads the first trace column as "
        "time; set include_step: true to use the Webots CSV log with MC2",
        'webots.csv.delimiter \',\' cannot be read by MC2; use " " (or ";" with '
        "the MC2 -snoopy option)",
    ]


def test_models_without_webots_log_keep_the_nnc_sim_warning():
    transformer, system = _transformer_with_webots_log(
        MC2 / "input" / "imported_mc2.yaml"
    )
    transformer.transform_files(system)

    assert transformer.warnings == [
        "MC2 trace columns are not root outputs, so nnc-sim traces will not "
        "contain them: sensor0__level, sample"
    ]


def test_no_warnings_when_every_column_is_an_output(tmp_path):
    path = _model(
        tmp_path,
        "verification:\n  backends:\n    mc2:\n      raw:\n"
        '        - id: q\n          code: "P=?[ F([${x}] > 1) ]"\n',
    )
    transformer, system = _transformer_for(path)
    transformer.transform_files(system)

    assert transformer.warnings == []


def test_folded_style_produces_one_query(tmp_path):
    path = _model(
        tmp_path,
        "verification:\n  backends:\n    mc2:\n      raw:\n"
        "        - id: q\n          code: >-\n"
        "            P=?[ F([${x}] > 1)\n            ]\n",
    )
    transformer, system = _transformer_for(path)

    assert transformer.transform(system) == "P=?[ F([x] > 1) ]\n"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (3.0, "3"),
        (-1.0, "-1"),
        (2.5, "2.5"),
        (1e-05, "0.00001"),
        (1e20, "100000000000000000000"),
    ],
)
def test_render_literal_avoids_exponent_notation(value, expected):
    assert render_literal(value) == expected


def test_render_literal_rejects_non_finite_values():
    with pytest.raises(ValueError, match="non-finite"):
        render_literal(float("inf"))


def test_requires_configuration_for_the_system(tmp_path):
    system = NncSystem.from_yaml(str(_model(tmp_path, "")))

    with pytest.raises(ValueError, match="Missing verification configuration"):
        Mc2Transformer().transform_files(system)
