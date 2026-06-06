"""Regression tests for YAML expressions that start with ``!``."""

from nnc import NncSystem


def test_yaml_loader_accepts_bang_prefixed_boolean_expressions(tmp_path):
    source = tmp_path / "bang_guard.yaml"
    source.write_text(
        """
module:
  name: bang_guard
cells:
  - id: 1
    contents:
      - x = 0
      - y = 0
    output:
      - y
rules:
  - consumer: y
    producer: "1"
    guard: !false
""".lstrip(),
        encoding="utf-8",
    )

    system = NncSystem.from_yaml(str(source))

    assert system.step() == {"y": 1.0}


def test_yaml_loader_accepts_bang_prefixed_grouped_expressions(tmp_path):
    source = tmp_path / "bang_group.yaml"
    source.write_text(
        """
module:
  name: bang_group
cells:
  - id: 1
    contents:
      - x = 0
      - y = 0
    output:
      - y
rules:
  - consumer: y
    producer: "1"
    guard: !(x > 1)
""".lstrip(),
        encoding="utf-8",
    )

    system = NncSystem.from_yaml(str(source))

    assert system.step() == {"y": 1.0}
