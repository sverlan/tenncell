"""Contract tests for root module YAML includes."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from nnc import NncSystem
from nnc.inputs.yaml.errors import YamlLocatedError
from nnc.inputs.yaml.includes import load_yaml_with_includes


def _write(path: Path, content: str) -> Path:
    path.write_text(content.lstrip(), encoding="utf-8")
    return path


def _workspace_temp_dir():
    return TemporaryDirectory(dir=Path(__file__).resolve().parents[3])


def test_yaml_loader_executes_included_functional_fixture():
    path = (
        Path(__file__).resolve().parents[2]
        / "fixtures"
        / "functional"
        / "include"
        / "main.yaml"
    )
    system = NncSystem.from_yaml(str(path))

    assert list(system.output_variables) == ["x"]
    assert system.step() == {"x": 5.0}


def test_yaml_loader_caches_effective_included_document():
    path = (
        Path(__file__).resolve().parents[2]
        / "fixtures"
        / "functional"
        / "include"
        / "main.yaml"
    )
    raw_cache = {}
    system = NncSystem.from_yaml(str(path), _raw_data_cache=raw_cache)

    assert raw_cache[system.source_path]["constants"] == {"START": 1}
    assert raw_cache[system.source_path]["rules"] == [
        "x + 2 -> x",
        "x + 1 -> x",
    ]


def test_include_locations_point_to_fragment_rules():
    with _workspace_temp_dir() as tmp_dir:
        tmp_path = Path(tmp_dir)
        root = _write(
            tmp_path / "root.yaml",
            """
module:
  name: include_bad_rule
  include: rules.yaml
cells:
  - id: 1
    contents:
      - x = 0
""",
        )
        rules = _write(
            tmp_path / "rules.yaml",
            """
rules:
  - missing + 1 -> x
""",
        )

        with pytest.raises(YamlLocatedError) as error_info:
            NncSystem.from_yaml(str(root))

        assert error_info.value.source_path == rules
        assert error_info.value.line == 2


def test_include_locations_point_to_fragment_constants():
    with _workspace_temp_dir() as tmp_dir:
        tmp_path = Path(tmp_dir)
        root = _write(
            tmp_path / "root.yaml",
            """
module:
  include: constants.yaml
cells:
  - id: 1
    contents:
      - x = 0
""",
        )
        constants = _write(
            tmp_path / "constants.yaml",
            """
constants:
  BAD: UNKNOWN + 1
""",
        )

        with pytest.raises(YamlLocatedError) as error_info:
            NncSystem.from_yaml(str(root))

        assert error_info.value.source_path == constants
        assert error_info.value.line == 2


def test_include_locations_point_to_fragment_backend_metadata():
    with _workspace_temp_dir() as tmp_dir:
        tmp_path = Path(tmp_dir)
        root = _write(
            tmp_path / "root.yaml",
            """
module:
  name: include_bad_webots
  include: webots.yaml
cells:
  - id: 1
    contents:
      - x = 0
    output: [x]
""",
        )
        webots = _write(
            tmp_path / "webots.yaml",
            """
webots:
  controller_name: 3
""",
        )
        raw_cache = {}
        system = NncSystem.from_yaml(str(root), _raw_data_cache=raw_cache)

        from nnc.inputs.yaml.sections import YamlSectionContext
        from nnc.transformers.webots.webots_yaml_section_parser import (
            parse_webots_section,
        )

        with pytest.raises(YamlLocatedError) as error_info:
            parse_webots_section(
                raw_cache[system.source_path]["webots"],
                YamlSectionContext(
                    source_path=system.source_path,
                    import_paths=[],
                    header_cache={},
                    raw_data=raw_cache[system.source_path],
                    locations=system.source_locations,
                ),
            )

        assert error_info.value.source_path == webots
        assert error_info.value.line == 2


def test_include_locations_point_to_fragment_verilog_metadata():
    with _workspace_temp_dir() as tmp_dir:
        tmp_path = Path(tmp_dir)
        root = _write(
            tmp_path / "root.yaml",
            """
module:
  name: include_bad_verilog
  include: verilog.yaml
cells:
  - id: 1
    contents:
      - x = 0
    output: [x]
""",
        )
        verilog = _write(
            tmp_path / "verilog.yaml",
            """
verilog:
  real_encoding:
    kind: fixed_point
    width: 16
""",
        )
        raw_cache = {}
        system = NncSystem.from_yaml(str(root), _raw_data_cache=raw_cache)

        from nnc.inputs.yaml.sections import YamlSectionContext
        from nnc.transformers.verilog.verilog_yaml_section_parser import (
            parse_verilog_section,
        )

        with pytest.raises(YamlLocatedError) as error_info:
            parse_verilog_section(
                raw_cache[system.source_path]["verilog"],
                YamlSectionContext(
                    source_path=system.source_path,
                    import_paths=[],
                    header_cache={},
                    raw_data=raw_cache[system.source_path],
                    locations=system.source_locations,
                ),
            )

        assert error_info.value.source_path == verilog
        assert error_info.value.line == 3


def test_module_include_merges_backend_metadata():
    with _workspace_temp_dir() as tmp_dir:
        tmp_path = Path(tmp_dir)
        root = _write(
            tmp_path / "root.yaml",
            """
module:
  name: include_backend
  include:
    - verilog.yaml
    - webots.yaml
verilog:
  real_encoding:
    signed: false
webots:
  csv:
    variables: [y]
""",
        )
        _write(
            tmp_path / "verilog.yaml",
            """
verilog:
  real_encoding:
    kind: fixed_point
    width: 16
    frac_bits: 8
  ports:
    x:
      direction: output
""",
        )
        _write(
            tmp_path / "webots.yaml",
            """
webots:
  controller_name: robot
  csv:
    file: trace.csv
    variables: [x]
""",
        )

        data, _ = load_yaml_with_includes(root)

    assert data["verilog"]["real_encoding"] == {
        "kind": "fixed_point",
        "width": 16,
        "frac_bits": 8,
        "signed": False,
    }
    assert data["verilog"]["ports"] == {"x": {"direction": "output"}}
    assert data["webots"]["csv"]["variables"] == ["x", "y"]


def test_include_list_order_is_includes_then_root():
    with _workspace_temp_dir() as tmp_dir:
        tmp_path = Path(tmp_dir)
        root = _write(
            tmp_path / "root.yaml",
            """
module:
  name: include_order
  include: rules.yaml
rules:
  - root -> x
""",
        )
        _write(
            tmp_path / "rules.yaml",
            """
rules:
  - included -> x
""",
        )

        data, _ = load_yaml_with_includes(root)

    assert data["rules"] == ["included -> x", "root -> x"]


def test_include_resolves_through_import_paths():
    with _workspace_temp_dir() as tmp_dir:
        tmp_path = Path(tmp_dir)
        include_dir = tmp_path / "includes"
        include_dir.mkdir()
        root = _write(
            tmp_path / "root.yaml",
            """
module:
  name: import_path_include
  include: rules.yaml
""",
        )
        _write(
            include_dir / "rules.yaml",
            """
rules:
  - x -> y
""",
        )

        data, _ = load_yaml_with_includes(root, [include_dir])

    assert data["rules"] == ["x -> y"]


@pytest.mark.parametrize(
    ("root_text", "message"),
    [
        (
            """
include: rules.yaml
""",
            "module.include",
        ),
        (
            """
module:
  include: 3
""",
            "string or list",
        ),
        (
            """
module:
  include: [3]
""",
            "entries must be strings",
        ),
    ],
)
def test_include_rejects_invalid_declarations(root_text, message):
    with _workspace_temp_dir() as tmp_dir:
        root = _write(Path(tmp_dir) / "root.yaml", root_text)

        with pytest.raises(YamlLocatedError, match=message):
            load_yaml_with_includes(root)


def test_include_rejects_missing_file():
    with _workspace_temp_dir() as tmp_dir:
        root = _write(
            Path(tmp_dir) / "root.yaml",
            """
module:
  include: missing.yaml
""",
        )

        with pytest.raises(YamlLocatedError, match="Could not resolve include"):
            load_yaml_with_includes(root)


def test_include_rejects_non_mapping_fragment():
    with _workspace_temp_dir() as tmp_dir:
        tmp_path = Path(tmp_dir)
        root = _write(
            tmp_path / "root.yaml",
            """
module:
  include: rules.yaml
""",
        )
        _write(
            tmp_path / "rules.yaml",
            """
- x -> y
""",
        )

        with pytest.raises(YamlLocatedError, match="must be a mapping"):
            load_yaml_with_includes(root)


def test_include_rejects_module_section_in_fragment():
    with _workspace_temp_dir() as tmp_dir:
        tmp_path = Path(tmp_dir)
        root = _write(
            tmp_path / "root.yaml",
            """
module:
  include: fragment.yaml
""",
        )
        _write(
            tmp_path / "fragment.yaml",
            """
module:
  name: fragment
""",
        )

        with pytest.raises(YamlLocatedError, match="must not contain a module"):
            load_yaml_with_includes(root)


def test_include_rejects_conflicting_scalar_values():
    with _workspace_temp_dir() as tmp_dir:
        tmp_path = Path(tmp_dir)
        root = _write(
            tmp_path / "root.yaml",
            """
module:
  include: webots.yaml
webots:
  timestep: 64
""",
        )
        _write(
            tmp_path / "webots.yaml",
            """
webots:
  timestep: 32
""",
        )

        with pytest.raises(YamlLocatedError, match="Conflicting YAML include value"):
            load_yaml_with_includes(root)
