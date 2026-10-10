from pathlib import Path
import math

import pytest

from nnc.inputs.yaml.errors import YamlLocatedError
from nnc.inputs.yaml.locations import load_yaml_data_and_locations
from nnc.inputs.yaml.sections import YamlSectionContext
from nnc.transformers.webots.webots_yaml_section_parser import parse_webots_section


def _fixture_path(name: str) -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "fixtures"
        / "transformers"
        / "webots"
        / "input"
        / name
    )


def _context(path: Path) -> YamlSectionContext:
    data, locations = load_yaml_data_and_locations(path)
    return YamlSectionContext(
        source_path=path,
        import_paths=[],
        header_cache={},
        raw_data=data,
        locations=locations,
    )


def test_parse_webots_section_rejects_invalid_controller_name():
    path = _fixture_path("invalid_controller_name.yaml")
    context = _context(path)
    with pytest.raises(
        YamlLocatedError,
        match=r"invalid_controller_name\.yaml:2: webots\.controller_name must be a string if provided",
    ):
        parse_webots_section(context.raw_data["webots"], context)


def test_parse_webots_section_rejects_invalid_timestep():
    path = _fixture_path("invalid_timestep.yaml")
    context = _context(path)
    with pytest.raises(
        YamlLocatedError,
        match=r"invalid_timestep\.yaml:2: webots\.timestep must be an integer if provided",
    ):
        parse_webots_section(context.raw_data["webots"], context)


def test_parse_webots_section_rejects_invalid_bindings_and_init():
    path = _fixture_path("invalid_bindings_init.yaml")
    context = _context(path)
    with pytest.raises(
        YamlLocatedError,
        match=r"invalid_bindings_init\.yaml:2: webots\.bindings must be a mapping if provided",
    ):
        parse_webots_section(context.raw_data["webots"], context)


def test_parse_webots_section_rejects_invalid_init():
    path = _fixture_path("invalid_init.yaml")
    context = _context(path)
    with pytest.raises(
        YamlLocatedError,
        match=r"invalid_init\.yaml:6: webots\.init must be a mapping if provided",
    ):
        parse_webots_section(context.raw_data["webots"], context)


def test_parse_webots_section_rejects_invalid_binding_method_types():
    path = _fixture_path("invalid_binding_method.yaml")
    context = _context(path)
    with pytest.raises(
        YamlLocatedError,
        match=r"invalid_binding_method\.yaml:5: Webots binding 'led' read_method must be a string",
    ):
        parse_webots_section(context.raw_data["webots"], context)


def test_parse_webots_section_normalizes_special_init_values():
    path = _fixture_path("special_init_values.yaml")
    context = _context(path)
    config = parse_webots_section(context.raw_data["webots"], context)

    assert config.init["left_position"] == float("inf")
    assert math.isnan(config.init["right_position"])


def test_parse_webots_section_parses_csv_logging():
    path = _fixture_path("sensor_led_csv.yaml")
    context = _context(path)
    config = parse_webots_section(context.raw_data["webots"], context)

    assert config.csv is not None
    assert config.csv.file == "sensor_led.csv"
    assert config.csv.variables == ["input_x", "out"]
    assert config.csv.include_step is True
    assert config.csv.include_time is True
    assert config.csv.include_initial is False
    assert config.csv.delimiter == ";"
    assert config.csv.precision == 2


def test_parse_webots_section_parses_initial_csv_logging():
    path = _fixture_path("sensor_led_csv_initial.yaml")
    context = _context(path)
    config = parse_webots_section(context.raw_data["webots"], context)

    assert config.csv is not None
    assert config.csv.include_initial is True


@pytest.mark.parametrize(
    ("fixture", "message"),
    [
        (
            "invalid_csv.yaml",
            r"invalid_csv\.yaml:2: webots\.csv must be a mapping if provided",
        ),
        (
            "invalid_csv_file.yaml",
            r"invalid_csv_file\.yaml:3: webots\.csv\.file must be a string",
        ),
        (
            "invalid_csv_variables.yaml",
            r"invalid_csv_variables\.yaml:4: webots\.csv\.variables must be a list of strings",
        ),
        (
            "invalid_csv_include_step.yaml",
            r"invalid_csv_include_step\.yaml:5: webots\.csv\.include_step must be a boolean if provided",
        ),
        (
            "invalid_csv_include_time.yaml",
            r"invalid_csv_include_time\.yaml:5: webots\.csv\.include_time must be a boolean if provided",
        ),
        (
            "invalid_csv_include_initial.yaml",
            r"invalid_csv_include_initial\.yaml:5: webots\.csv\.include_initial must be a boolean if provided",
        ),
        (
            "invalid_csv_delimiter.yaml",
            r"invalid_csv_delimiter\.yaml:5: webots\.csv\.delimiter must be a non-empty string",
        ),
        (
            "invalid_csv_precision.yaml",
            r"invalid_csv_precision\.yaml:5: webots\.csv\.precision must be a non-negative integer or null",
        ),
    ],
)
def test_parse_webots_section_rejects_invalid_csv(fixture, message):
    path = _fixture_path(fixture)
    context = _context(path)

    with pytest.raises(YamlLocatedError, match=message):
        parse_webots_section(context.raw_data["webots"], context)


def test_parse_webots_section_reads_code_inline_and_from_files():
    path = _fixture_path("code_points.yaml")
    context = _context(path)

    code = parse_webots_section(context.raw_data["webots"], context).code

    assert list(code) == ["module", "setup", "before_step", "after_step", "shutdown"]
    assert code["setup"].source == "inline"
    assert code["setup"].text == 'mark("setup", timestep)'
    assert code["module"].source == "code/module.py"
    assert code["module"].text.startswith("def mark(*words):\n")
    # Relative indentation and inner blank lines are kept, trailing ones go.
    assert code["after_step"].text == (
        'mark("after_step", variables["speed"])\n\n'
        'if variables["speed"] > 1:\n    mark("fast")'
    )


def test_parse_webots_section_dedents_code_and_drops_empty_points(tmp_path):
    # Indented code, CRLF line endings, blank lines around it.
    (tmp_path / "setup.py").write_bytes(b"\r\n    a = 1\r\n\r\n      b = 2\r\n\r\n")
    path = tmp_path / "model.yaml"
    path.write_text(
        "webots:\n  code:\n    setup: {file: setup.py}\n    shutdown: '  '\n",
        encoding="utf-8",
    )
    context = _context(path)

    code = parse_webots_section(context.raw_data["webots"], context).code

    assert list(code) == ["setup"]
    assert code["setup"].text == "a = 1\n\n  b = 2"


@pytest.mark.parametrize(
    ("code", "message"),
    [
        ("code: [x]", r"model\.yaml:3: webots\.code must be a mapping"),
        (
            "code:\n    loop: x",
            r"model\.yaml:4: unknown webots\.code insertion point 'loop'; expected "
            r"one of module, setup, before_step, after_step, shutdown",
        ),
        (
            "code:\n    setup: 3",
            r"model\.yaml:4: webots\.code\.setup must be a string or a mapping "
            r"with only 'file'",
        ),
        (
            "code:\n    setup: {file: a.py, extra: 1}",
            r"webots\.code\.setup must be a string or a mapping with only 'file'",
        ),
        (
            "code:\n    setup: {file: ''}",
            r"model\.yaml:4: webots\.code\.setup\.file must be a non-empty string",
        ),
        (
            "code:\n    setup: {file: missing.py}",
            r"model\.yaml:4: webots\.code\.setup: cannot read .*missing\.py",
        ),
    ],
)
def test_parse_webots_section_rejects_invalid_code(tmp_path, code, message):
    path = tmp_path / "model.yaml"
    path.write_text(f"webots:\n  timestep: 32\n  {code}\n", encoding="utf-8")
    context = _context(path)

    with pytest.raises(YamlLocatedError, match=message):
        parse_webots_section(context.raw_data["webots"], context)


@pytest.mark.parametrize(
    "file_name",
    [
        "C:/code/setup.py",
        "/code/setup.py",
        "\\\\host\\share\\setup.py",
        "\\code\\setup.py",
    ],
)
def test_parse_webots_section_rejects_absolute_code_file_paths(tmp_path, file_name):
    # A drive or root would discard the declaring file's folder.
    path = tmp_path / "model.yaml"
    path.write_text(
        f"webots:\n  code:\n    setup: {{file: '{file_name}'}}\n", encoding="utf-8"
    )
    context = _context(path)

    with pytest.raises(
        YamlLocatedError,
        match=r"model\.yaml:3: webots\.code\.setup\.file must be relative to the "
        r"YAML file that declares it",
    ):
        parse_webots_section(context.raw_data["webots"], context)


def test_parse_webots_section_rejects_code_files_that_are_not_utf8(tmp_path):
    (tmp_path / "latin.py").write_bytes(b"print('\xe9')\n")
    path = tmp_path / "model.yaml"
    path.write_text("webots:\n  code:\n    setup: {file: latin.py}\n", encoding="utf-8")
    context = _context(path)

    with pytest.raises(YamlLocatedError, match=r"cannot read .*latin\.py"):
        parse_webots_section(context.raw_data["webots"], context)


def test_parse_webots_section_drops_a_utf8_bom_from_code_files(tmp_path):
    (tmp_path / "setup.py").write_bytes(b"\xef\xbb\xbfa = 1\n")
    path = tmp_path / "model.yaml"
    path.write_text("webots:\n  code:\n    setup: {file: setup.py}\n", encoding="utf-8")
    context = _context(path)

    code = parse_webots_section(context.raw_data["webots"], context).code

    assert code["setup"].text == "a = 1"


@pytest.mark.parametrize(
    ("key", "method"),
    [
        ("read_method", "getValue and (lambda: 0.0)"),
        ("write_method", "set.__call__"),
    ],
)
def test_parse_webots_section_keeps_expression_methods_with_a_warning(
    tmp_path, key, method
):
    # An expression here is pasted after `devices[...].`; it still works,
    # with a located warning pointing to webots.code.
    path = tmp_path / "model.yaml"
    path.write_text(
        f"webots:\n  bindings:\n    x:\n      device: d\n      {key}: {method!r}\n",
        encoding="utf-8",
    )
    context = _context(path)

    config = parse_webots_section(context.raw_data["webots"], context)

    assert getattr(config.bindings["x"], key) == method
    (warning,) = config.warnings
    assert warning.endswith(
        f"model.yaml:5: Webots binding 'x' {key} is not a method name; the text is "
        "pasted into the controller unchecked. Prefer a method added to the device "
        "in webots.code.setup"
    )


@pytest.mark.parametrize(
    ("key", "method"),
    [("write_method", "class"), ("read_method", ""), ("read_method", "  ")],
)
def test_parse_webots_section_rejects_empty_or_keyword_methods(tmp_path, key, method):
    path = tmp_path / "model.yaml"
    path.write_text(
        f"webots:\n  bindings:\n    x:\n      device: d\n      {key}: {method!r}\n",
        encoding="utf-8",
    )
    context = _context(path)

    with pytest.raises(
        YamlLocatedError,
        match=rf"model\.yaml:5: Webots binding 'x' {key} must be a method name",
    ):
        parse_webots_section(context.raw_data["webots"], context)


@pytest.mark.parametrize("method", ["getValue", "match", "type", "lire_capteur_é"])
def test_parse_webots_section_accepts_any_identifier_as_method_name(tmp_path, method):
    # Soft keywords (match, type) and Unicode identifiers are valid names.
    path = tmp_path / "model.yaml"
    path.write_text(
        f"webots:\n  bindings:\n    x:\n      device: d\n      read_method: {method}\n",
        encoding="utf-8",
    )
    context = _context(path)

    config = parse_webots_section(context.raw_data["webots"], context)

    assert config.bindings["x"].read_method == method
    assert config.warnings == []


def test_parse_webots_section_accepts_bindings_without_device(tmp_path):
    # A virtual device: webots.code.setup provides devices['x'].
    path = tmp_path / "model.yaml"
    path.write_text(
        "webots:\n  bindings:\n    x:\n      read_method: read\n", encoding="utf-8"
    )
    context = _context(path)

    binding = parse_webots_section(context.raw_data["webots"], context).bindings["x"]

    assert binding.device is None


@pytest.mark.parametrize("device", ["''", "3", "[ps0]", "null"])
def test_parse_webots_section_rejects_devices_that_are_not_names(tmp_path, device):
    path = tmp_path / "model.yaml"
    path.write_text(
        f"webots:\n  bindings:\n    x:\n      device: {device}\n      read_method: read\n",
        encoding="utf-8",
    )
    context = _context(path)

    with pytest.raises(
        YamlLocatedError,
        match=r"model\.yaml:4: Webots binding 'x' device must be a non-empty string",
    ):
        parse_webots_section(context.raw_data["webots"], context)
