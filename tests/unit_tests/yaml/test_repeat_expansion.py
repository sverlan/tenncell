"""Contract tests for YAML repeat-list expansion."""

from pathlib import Path

import pytest

from nnc import NncSystem
from nnc.inputs.yaml.errors import YamlLocatedError
from nnc.inputs.yaml.locations import YamlLocationIndex
from nnc.inputs.yaml.lowering.repeat import expand_repeat_items, unwrap_expanded_items


def _locations() -> YamlLocationIndex:
    return YamlLocationIndex(Path("repeat.yaml"), {})


def _expand(items):
    return unwrap_expanded_items(expand_repeat_items(items, _locations(), ("rules",)))


def test_repeat_expands_rule_list_items():
    expanded = _expand(
        [
            {
                "repeat": {
                    "var": "i",
                    "range": [0, 2],
                    "body": ["x_${i} + 1 -> x_${i}"],
                }
            }
        ]
    )

    assert expanded == [
        "x_0 + 1 -> x_0",
        "x_1 + 1 -> x_1",
        "x_2 + 1 -> x_2",
    ]


def test_repeat_expands_scalar_placeholders_to_integers():
    expanded = expand_repeat_items(
        [
            {
                "repeat": {
                    "var": "i",
                    "range": [1, 2],
                    "body": [{"id": "${i+1}"}],
                }
            }
        ],
        _locations(),
        ("items",),
    )

    assert unwrap_expanded_items(expanded) == [{"id": 2}, {"id": 3}]


def test_repeat_expands_input_output_style_lists():
    expanded = _expand(
        [
            {
                "repeat": {
                    "var": "i",
                    "range": [0, 2],
                    "body": ["x_${i}"],
                }
            }
        ]
    )

    assert expanded == ["x_0", "x_1", "x_2"]


def test_nested_repeat_expands_cartesian_product():
    expanded = _expand(
        [
            {
                "repeat": {
                    "var": "i",
                    "range": [0, 1],
                    "body": [
                        {
                            "repeat": {
                                "var": "j",
                                "range": [0, 1],
                                "body": ["x_${i}_${j} = ${i}"],
                            }
                        }
                    ],
                }
            }
        ]
    )

    assert expanded == [
        "x_0_0 = 0",
        "x_0_1 = 0",
        "x_1_0 = 1",
        "x_1_1 = 1",
    ]


@pytest.mark.parametrize(
    ("raw_range", "message"),
    [
        ([0, 1.5], "integers"),
        ([0, 2, 0], "zero"),
        ([2, 0, 1], "negative"),
        ([0, 2, -1], "positive"),
        ([0, 3, 2], "reached exactly"),
    ],
)
def test_repeat_rejects_invalid_ranges(raw_range, message):
    with pytest.raises(YamlLocatedError, match=message):
        _expand(
            [
                {
                    "repeat": {
                        "var": "i",
                        "range": raw_range,
                        "body": ["x_${i} = ${i}"],
                    }
                }
            ]
        )


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (["x_${missing} = 0"], "Unknown repeat placeholder"),
        (["x_${i+0} = 0"], "Invalid repeat placeholder"),
        (["x_${i+-1} = 0"], "Invalid repeat placeholder"),
        (["x_${i--1} = 0"], "Invalid repeat placeholder"),
        (["x_${i*2} = 0"], "Invalid repeat placeholder"),
    ],
)
def test_repeat_rejects_invalid_placeholders(body, message):
    with pytest.raises(YamlLocatedError, match=message):
        _expand([{"repeat": {"var": "i", "range": [0, 1], "body": body}}])


def test_repeat_rejects_nested_variable_shadowing():
    with pytest.raises(YamlLocatedError, match="shadows an active repeat variable"):
        _expand(
            [
                {
                    "repeat": {
                        "var": "i",
                        "range": [0, 1],
                        "body": [
                            {
                                "repeat": {
                                    "var": "i",
                                    "range": [0, 1],
                                    "body": ["x_${i} = ${i}"],
                                }
                            }
                        ],
                    }
                }
            ]
        )


def test_repeat_rejects_non_list_body():
    with pytest.raises(YamlLocatedError, match="repeat.body must be a list"):
        _expand([{"repeat": {"var": "i", "range": [0, 1], "body": "x_${i} = 0"}}])


def test_yaml_loader_executes_repeat_fixture():
    path = Path(__file__).resolve().parents[2] / "fixtures" / "functional" / "repeat.yaml"
    system = NncSystem.from_yaml(str(path))

    assert sorted(system.variables) == ["x_0", "x_1", "x_2"]
    assert list(system.output_variables) == ["x_0", "x_1", "x_2"]
    assert system.step() == {"x_0": 1.0, "x_1": 2.0, "x_2": 3.0}


def test_yaml_loader_rejects_top_level_cell_repeat(tmp_path):
    source = tmp_path / "top_cell_repeat.yaml"
    source.write_text(
        """
cells:
  - repeat:
      var: i
      range: [0, 1]
      body:
        - id: ${i}
          contents:
            - x_${i} = 0
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(YamlLocatedError, match="top-level cells"):
        NncSystem.from_yaml(str(source))
