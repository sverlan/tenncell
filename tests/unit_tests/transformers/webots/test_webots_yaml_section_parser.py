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
        ("invalid_csv.yaml", r"invalid_csv\.yaml:2: webots\.csv must be a mapping if provided"),
        ("invalid_csv_file.yaml", r"invalid_csv_file\.yaml:3: webots\.csv\.file must be a string"),
        ("invalid_csv_variables.yaml", r"invalid_csv_variables\.yaml:4: webots\.csv\.variables must be a list of strings"),
        ("invalid_csv_include_step.yaml", r"invalid_csv_include_step\.yaml:5: webots\.csv\.include_step must be a boolean if provided"),
        ("invalid_csv_include_time.yaml", r"invalid_csv_include_time\.yaml:5: webots\.csv\.include_time must be a boolean if provided"),
        ("invalid_csv_include_initial.yaml", r"invalid_csv_include_initial\.yaml:5: webots\.csv\.include_initial must be a boolean if provided"),
        ("invalid_csv_delimiter.yaml", r"invalid_csv_delimiter\.yaml:5: webots\.csv\.delimiter must be a non-empty string"),
        ("invalid_csv_precision.yaml", r"invalid_csv_precision\.yaml:5: webots\.csv\.precision must be a non-negative integer or null"),
    ],
)
def test_parse_webots_section_rejects_invalid_csv(fixture, message):
    path = _fixture_path(fixture)
    context = _context(path)

    with pytest.raises(YamlLocatedError, match=message):
        parse_webots_section(context.raw_data["webots"], context)
