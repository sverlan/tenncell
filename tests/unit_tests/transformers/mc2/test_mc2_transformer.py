"""Contract tests for the MC2 raw verification transformer."""

from pathlib import Path

import pytest

from nnc import NncSystem
from nnc.cli_transform import _parse_verification_configs
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
    ],
)
def test_emits_golden_mc2_files(path, stem):
    transformer, system = _transformer_for(path)

    files = transformer.transform_files(system)

    assert files == _expected(stem)
    assert transformer.transform(system) == files[".mc2.pltl"]
    assert transformer.get_file_extension() == ".mc2.pltl"


def test_warns_about_generic_properties_targeting_mc2():
    transformer, system = _transformer_for(
        FIXTURES / "verification" / "input" / "fsm_counter_mc2.yaml"
    )
    transformer.transform_files(system)

    assert transformer.warnings == [
        "generic verification properties are not emitted by the MC2 raw backend "
        "yet: bounded",
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
def test_requires_mc2_raw_entries(tmp_path, verification):
    transformer, system = _transformer_for(_model(tmp_path, verification))

    with pytest.raises(ValueError, match=r"No MC2 raw verification entries found"):
        transformer.transform_files(system)


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
