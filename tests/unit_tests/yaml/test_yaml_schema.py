"""Contract tests for how TENNCell YAML resolves plain (unquoted) values."""

import math
from pathlib import Path

import pytest

from nnc import NncSystem
from nnc.inputs.yaml.errors import YamlLocatedError
from nnc.inputs.yaml.locations import load_yaml_data_and_locations
from nnc.inputs.yaml.sections import YamlSectionContext
from nnc.transformers.verilog.verilog_yaml_section_parser import parse_verilog_section


def _load_value(tmp_path: Path, text: str):
    path = tmp_path / "value.yaml"
    path.write_text(f"k: {text}\n", encoding="utf-8")
    data, _ = load_yaml_data_and_locations(path)
    return data["k"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # YAML 1.1 booleans are plain strings
        ("on", "on"),
        ("OFF", "OFF"),
        ("yes", "yes"),
        ("No", "No"),
        # YAML 1.2 booleans
        ("true", True),
        ("False", False),
        ("TRUE", True),
        # null
        ("null", None),
        ("~", None),
        ("", None),
        # integers: a leading zero is decimal; hex, binary and underscores kept
        ("010", 10),
        ("0777", 777),
        ("0x1F", 31),
        ("-0x10", -16),
        ("0b101", 5),
        ("0o17", 15),
        ("-0o10", -8),
        ("1_000", 1000),
        ("-42", -42),
        # floats: an exponent alone makes a float
        ("1e5", 100000.0),
        ("1.5e-3", 0.0015),
        ("-2.5", -2.5),
        (".5", 0.5),
        ("1_000.5", 1000.5),
        (".inf", math.inf),
        ("-.inf", -math.inf),
        # YAML 1.1-only forms stay strings
        ("1:30", "1:30"),
        ("2026-10-08", "2026-10-08"),
        ("=", "="),
        ("0b2", "0b2"),
        ("0o8", "0o8"),
    ],
)
def test_plain_values_follow_yaml_1_2_core_rules(tmp_path, text, expected):
    value = _load_value(tmp_path, text)

    assert value == expected
    assert type(value) is type(expected)


def test_nan_is_a_float(tmp_path):
    value = _load_value(tmp_path, ".nan")
    assert isinstance(value, float) and math.isnan(value)


def test_plain_keys_follow_the_same_rules(tmp_path):
    path = tmp_path / "keys.yaml"
    path.write_text("on: 1\nOFF: 2\n010: 3\nnull: 4\n", encoding="utf-8")

    data, _ = load_yaml_data_and_locations(path)

    assert data == {"on": 1, "OFF": 2, 10: 3, None: 4}


def test_locations_are_indexed_by_resolved_keys(tmp_path):
    path = tmp_path / "keys.yaml"
    path.write_text("m:\n  010: a\n  true: b\n  null: c\n  name: d\n", encoding="utf-8")

    data, locations = load_yaml_data_and_locations(path)

    assert {key: locations.line_for("m", key) for key in data["m"]} == {
        10: 2,
        True: 3,
        None: 4,
        "name": 5,
    }


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "model.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_fsm_states_named_on_and_off(tmp_path):
    path = _write(
        tmp_path,
        "cells:\n  - id: 1\n    contents:\n      - st = 0, go = 0\n    input: [go]\n"
        "fsm:\n  - name: power\n    variable: st\n    initial: OFF\n    states:\n"
        "      - OFF:\n          rules:\n            - if: go > 0\n"
        "              then: ON -> st\n"
        "      - ON:\n          rules:\n            - st -> st\n",
    )
    system = NncSystem.from_yaml(str(path))

    system.step({"go": 1.0})

    assert system.constants["power__ON"].value == 1.0
    assert system.variables["st"].value.value == 1.0


def test_variable_named_on_and_cell_id_with_leading_zero(tmp_path):
    path = _write(
        tmp_path,
        "constants:\n  K: 1e5\ncells:\n  - id: 010\n    contents:\n"
        "      - on = 0, x = 0\n    input: [on]\n    output: [x]\n"
        "rules:\n  - on + K -> x\n",
    )
    system = NncSystem.from_yaml(str(path))

    assert [cell.id for cell in system.cells] == [10]
    assert system.constants["K"].value == 100000.0
    assert system.step({"on": 1.0}) == {"x": 100001.0}


@pytest.mark.parametrize("value", ["no", "off", '"false"', "0"])
def test_zero_reset_mode_must_be_a_boolean(tmp_path, value):
    path = _write(
        tmp_path,
        f"module:\n  zero_reset_mode: {value}\n"
        "cells:\n  - id: 1\n    contents:\n      - x = 1\n    output: [x]\n"
        "rules:\n  - 1 -> x\n",
    )

    with pytest.raises(
        YamlLocatedError,
        match=r"model\.yaml:2: module\.zero_reset_mode must be true or false",
    ):
        NncSystem.from_yaml(str(path))


def test_zero_reset_mode_accepts_booleans(tmp_path):
    path = _write(
        tmp_path,
        "module:\n  zero_reset_mode: false\n"
        "cells:\n  - id: 1\n    contents:\n      - x = 1\n    output: [x]\n"
        "rules:\n  - 1 -> x\n",
    )

    assert NncSystem.from_yaml(str(path)).module_config.zero_reset_mode is False


def _verilog_context(path: Path) -> tuple[dict, YamlSectionContext]:
    data, locations = load_yaml_data_and_locations(path)
    return data, YamlSectionContext(path, [], {}, data, locations)


@pytest.mark.parametrize(
    ("verilog", "message"),
    [
        (
            "  real_encoding: {kind: fixed, signed: yes, width: 16, frac_bits: 8}\n",
            r"model\.yaml:3: verilog\.real_encoding 'signed' must be true or false",
        ),
        (
            "  real_encoding: {kind: fixed, signed: true, width: 16, frac_bits: 8}\n"
            "  ports:\n    x:\n      direction: output\n      width: 8\n"
            '      signed: "true"\n',
            r"model\.yaml:8: verilog port 'x' 'signed' must be true or false",
        ),
    ],
)
def test_verilog_signed_must_be_a_boolean(tmp_path, verilog, message):
    path = _write(tmp_path, "cells: []\nverilog:\n" + verilog)
    data, context = _verilog_context(path)

    with pytest.raises(YamlLocatedError, match=message):
        parse_verilog_section(data["verilog"], context)
