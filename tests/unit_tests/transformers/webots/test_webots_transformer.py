"""Webots transformer contract tests."""

from pathlib import Path

from nnc.cli_transform import _parse_webots_configs
from nnc.model.system import NncSystem
from nnc.transformers import WebotsTransformer


def _fixture_path(name: str) -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "fixtures"
        / "transformers"
        / "webots"
        / name
    )


def test_webots_transformer_emits_controller():
    input_path = _fixture_path("input/sensor_led.yaml")
    expected_path = _fixture_path("expected/sensor_led.py")
    raw_cache: dict[Path, dict] = {}

    system = NncSystem.from_yaml(str(input_path), _raw_data_cache=raw_cache)
    transformer = WebotsTransformer()
    transformer.set_webots_configs(_parse_webots_configs([system], raw_cache))

    assert transformer.transform(system) == expected_path.read_text(encoding="utf-8")


def test_webots_transformer_emits_motor_initialization():
    input_path = _fixture_path("input/motor_velocity.yaml")
    expected_path = _fixture_path("expected/motor_velocity.py")
    raw_cache: dict[Path, dict] = {}

    system = NncSystem.from_yaml(str(input_path), _raw_data_cache=raw_cache)
    transformer = WebotsTransformer()
    transformer.set_webots_configs(_parse_webots_configs([system], raw_cache))

    assert transformer.transform(system) == expected_path.read_text(encoding="utf-8")


def test_webots_transformer_emits_csv_logging():
    input_path = _fixture_path("input/sensor_led_csv.yaml")
    expected_path = _fixture_path("expected/sensor_led_csv.py")
    raw_cache: dict[Path, dict] = {}

    system = NncSystem.from_yaml(str(input_path), _raw_data_cache=raw_cache)
    transformer = WebotsTransformer()
    transformer.set_webots_configs(_parse_webots_configs([system], raw_cache))

    assert transformer.transform(system) == expected_path.read_text(encoding="utf-8")


def test_webots_transformer_rejects_unknown_csv_variable():
    input_path = _fixture_path("input/sensor_led_csv_unknown_variable.yaml")
    raw_cache: dict[Path, dict] = {}

    system = NncSystem.from_yaml(str(input_path), _raw_data_cache=raw_cache)
    transformer = WebotsTransformer()
    transformer.set_webots_configs(_parse_webots_configs([system], raw_cache))

    try:
        transformer.transform(system)
    except ValueError as error:
        assert (
            "Webots CSV configuration references unknown TENNCell variable 'missing'"
            in str(error)
        )
    else:
        raise AssertionError("Expected unknown CSV variable validation error")
