"""Webots transformer contract tests."""

from pathlib import Path

import pytest

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


def test_expression_methods_are_reported_as_transformer_warnings():
    # nnc-gen prints transformer.warnings; they belong to the file just
    # transformed (a second file without expressions has none).
    raw_cache: dict[Path, dict] = {}
    expression = NncSystem.from_yaml(
        str(_fixture_path("input/expression_method.yaml")), _raw_data_cache=raw_cache
    )
    plain = NncSystem.from_yaml(
        str(_fixture_path("input/sensor_led.yaml")), _raw_data_cache=raw_cache
    )
    transformer = WebotsTransformer()
    transformer.set_webots_configs(
        _parse_webots_configs([expression, plain], raw_cache)
    )

    controller = transformer.transform(expression)

    (warning,) = transformer.warnings
    assert "expression_method.yaml:21: Webots binding 'distance' read_method" in warning
    assert "devices['distance'].getValue and (lambda:" in controller
    transformer.transform(plain)
    assert transformer.warnings == []


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


def test_webots_transformer_emits_initial_csv_row_when_configured():
    input_path = _fixture_path("input/sensor_led_csv_initial.yaml")
    expected_path = _fixture_path("expected/sensor_led_csv_initial.py")
    raw_cache: dict[Path, dict] = {}

    system = NncSystem.from_yaml(str(input_path), _raw_data_cache=raw_cache)
    transformer = WebotsTransformer()
    transformer.set_webots_configs(_parse_webots_configs([system], raw_cache))

    assert transformer.transform(system) == expected_path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("fixture", "message"),
    [
        (
            "unknown_bound_variable.yaml",
            r"unknown_bound_variable\.yaml:15: Webots configuration references "
            r"unknown TENNCell variable 'spead'",
        ),
        (
            "init_without_write.yaml",
            r"init_without_write\.yaml:15: Webots init references 'distance' "
            r"without a write method",
        ),
        (
            "missing_input_binding.yaml",
            # A missing binding points at the first entry of webots.bindings.
            r"missing_input_binding\.yaml:14: Webots configuration is missing an "
            r"input binding for 'input_x'",
        ),
        (
            "missing_output_binding.yaml",
            r"missing_output_binding\.yaml:14: Webots configuration is missing an "
            r"output binding for 'out'",
        ),
    ],
)
def test_binding_errors_name_their_yaml_line(fixture, message):
    input_path = _fixture_path(f"input/{fixture}")
    raw_cache: dict[Path, dict] = {}

    system = NncSystem.from_yaml(str(input_path), _raw_data_cache=raw_cache)
    transformer = WebotsTransformer()
    transformer.set_webots_configs(_parse_webots_configs([system], raw_cache))

    with pytest.raises(ValueError, match=message):
        transformer.transform(system)


def test_default_timestep_and_special_init_values_are_emitted():
    # No timestep: read from the robot; no outputs: the loop keeps its pass;
    # init values -inf and nan are written as float('-inf') and float('nan').
    input_path = _fixture_path("input/default_timestep_special_init.yaml")
    expected_path = _fixture_path("expected/default_timestep_special_init.py")
    raw_cache: dict[Path, dict] = {}

    system = NncSystem.from_yaml(str(input_path), _raw_data_cache=raw_cache)
    transformer = WebotsTransformer()
    transformer.set_webots_configs(_parse_webots_configs([system], raw_cache))

    assert transformer.transform(system) == expected_path.read_text(encoding="utf-8")


_MODEL = (
    "cells:\n  - id: 1\n    contents:\n      - speed = 0\n      - other = 0\n"
    "    output: [speed]\nrules:\n  - 1 -> speed\nwebots:\n  bindings:\n"
)
_WRITE = "    speed:\n      device: wheel\n      write_method: setVelocity\n"


def _line_of(text: str, needle: str) -> int:
    """1-based number of the one line of ``text`` whose content is ``needle``."""
    (number,) = [
        n for n, line in enumerate(text.splitlines(), 1) if line.strip() == needle
    ]
    return number


# YAML after `bindings:`, the content of the line the error must point to (an
# init entry, or the first field of the binding), and the message.
@pytest.mark.parametrize(
    ("webots", "needle", "message"),
    [
        (
            _WRITE + "  init:\n    ghost: 1\n",
            "ghost: 1",
            "Webots configuration references unknown TENNCell variable 'ghost'",
        ),
        (
            _WRITE + "  init:\n    other: 1\n",
            "other: 1",
            "Webots init references unknown binding 'other'",
        ),
        (
            "    speed:\n      device: wheel\n      read_method: getValue\n",
            "device: wheel",
            "Webots output binding 'speed' must define a write method",
        ),
    ],
)
def test_init_and_binding_errors_name_their_yaml_line(
    tmp_path, webots, needle, message
):
    path = tmp_path / "model.yaml"
    text = _MODEL + webots
    path.write_text(text, encoding="utf-8")
    raw_cache: dict[Path, dict] = {}
    system = NncSystem.from_yaml(str(path), _raw_data_cache=raw_cache)
    transformer = WebotsTransformer()
    transformer.set_webots_configs(_parse_webots_configs([system], raw_cache))

    with pytest.raises(
        ValueError, match=rf"model\.yaml:{_line_of(text, needle)}: {message}"
    ):
        transformer.transform(system)


def test_a_binding_without_methods_is_rejected_for_hand_built_configs(tmp_path):
    # The YAML parser already requires a method; the Python API can still
    # hand the transformer a binding without one.
    path = tmp_path / "model.yaml"
    text = _MODEL + _WRITE
    path.write_text(text, encoding="utf-8")
    raw_cache: dict[Path, dict] = {}
    system = NncSystem.from_yaml(str(path), _raw_data_cache=raw_cache)
    configs = _parse_webots_configs([system], raw_cache)
    configs[system.source_path].bindings["speed"].write_method = None
    transformer = WebotsTransformer(configs)
    line = _line_of(text, "device: wheel")

    with pytest.raises(
        ValueError,
        match=rf"model\.yaml:{line}: Webots binding 'speed' must define a read or write method",
    ):
        transformer.transform(system)


def test_export_needs_a_yaml_source_and_a_webots_config(tmp_path):
    path = tmp_path / "model.yaml"
    path.write_text(_MODEL + _WRITE, encoding="utf-8")
    raw_cache: dict[Path, dict] = {}
    system = NncSystem.from_yaml(str(path), _raw_data_cache=raw_cache)

    with pytest.raises(ValueError, match="Missing Webots configuration for"):
        WebotsTransformer().transform(system)
    system.source_path = None
    with pytest.raises(ValueError, match="requires systems loaded from YAML files"):
        WebotsTransformer().transform(system)


def test_webots_transformer_rejects_unknown_csv_variable():
    input_path = _fixture_path("input/sensor_led_csv_unknown_variable.yaml")
    raw_cache: dict[Path, dict] = {}

    system = NncSystem.from_yaml(str(input_path), _raw_data_cache=raw_cache)
    transformer = WebotsTransformer()
    transformer.set_webots_configs(_parse_webots_configs([system], raw_cache))

    try:
        transformer.transform(system)
    except ValueError as error:
        # Located at the CSV variable list.
        assert str(error).endswith(
            "sensor_led_csv_unknown_variable.yaml:24: Webots CSV configuration "
            "references unknown TENNCell variable 'missing'"
        )
    else:
        raise AssertionError("Expected unknown CSV variable validation error")


def test_webots_transformer_pastes_code_at_every_insertion_point():
    input_path = _fixture_path("input/code_points.yaml")
    expected_path = _fixture_path("expected/code_points.py")
    raw_cache: dict[Path, dict] = {}

    system = NncSystem.from_yaml(str(input_path), _raw_data_cache=raw_cache)
    transformer = WebotsTransformer()
    transformer.set_webots_configs(_parse_webots_configs([system], raw_cache))

    assert transformer.transform(system) == expected_path.read_text(encoding="utf-8")


def test_webots_code_file_paths_are_relative_to_the_declaring_fragment():
    input_path = _fixture_path("input/code_include.yaml")
    raw_cache: dict[Path, dict] = {}

    system = NncSystem.from_yaml(str(input_path), _raw_data_cache=raw_cache)
    transformer = WebotsTransformer()
    transformer.set_webots_configs(_parse_webots_configs([system], raw_cache))
    controller = transformer.transform(system)

    assert "    # webots code: setup (setup.py)\n" in controller
    assert '    print("setup from the fragment\'s folder")\n' in controller


def test_comment_only_code_in_a_model_without_inputs_or_outputs_compiles():
    input_path = _fixture_path("input/code_no_io.yaml")
    raw_cache: dict[Path, dict] = {}

    system = NncSystem.from_yaml(str(input_path), _raw_data_cache=raw_cache)
    transformer = WebotsTransformer()
    transformer.set_webots_configs(_parse_webots_configs([system], raw_cache))
    controller = transformer.transform(system)

    compile(controller, "code_no_io.py", "exec")
    for point in ("module", "setup", "before_step", "after_step", "shutdown"):
        assert f"# {point}\n" in controller


def test_setup_code_runs_before_enable_init_and_the_loop():
    # Methods added to devices in setup can serve reads, init and writes.
    input_path = _fixture_path("input/code_patch.yaml")
    expected_path = _fixture_path("expected/code_patch.py")
    raw_cache: dict[Path, dict] = {}

    system = NncSystem.from_yaml(str(input_path), _raw_data_cache=raw_cache)
    transformer = WebotsTransformer()
    transformer.set_webots_configs(_parse_webots_configs([system], raw_cache))

    assert transformer.transform(system) == expected_path.read_text(encoding="utf-8")


def test_virtual_devices_get_no_lookup_and_a_check_after_setup():
    input_path = _fixture_path("input/code_virtual.yaml")
    expected_path = _fixture_path("expected/code_virtual.py")
    raw_cache: dict[Path, dict] = {}

    system = NncSystem.from_yaml(str(input_path), _raw_data_cache=raw_cache)
    transformer = WebotsTransformer()
    transformer.set_webots_configs(_parse_webots_configs([system], raw_cache))

    assert transformer.transform(system) == expected_path.read_text(encoding="utf-8")


def test_a_virtual_device_without_setup_code_is_rejected():
    input_path = _fixture_path("input/code_virtual_no_setup.yaml")
    raw_cache: dict[Path, dict] = {}

    system = NncSystem.from_yaml(str(input_path), _raw_data_cache=raw_cache)
    transformer = WebotsTransformer()
    transformer.set_webots_configs(_parse_webots_configs([system], raw_cache))

    with pytest.raises(
        ValueError,
        match=r"code_virtual_no_setup\.yaml:16: Webots binding 'nearest' has no "
        r"device, so webots\.code\.setup must provide devices\['nearest'\]",
    ):
        transformer.transform(system)


def test_basic_binding_errors_come_before_the_missing_setup_check():
    input_path = _fixture_path("input/code_virtual_no_read.yaml")
    raw_cache: dict[Path, dict] = {}

    system = NncSystem.from_yaml(str(input_path), _raw_data_cache=raw_cache)
    transformer = WebotsTransformer()
    transformer.set_webots_configs(_parse_webots_configs([system], raw_cache))

    with pytest.raises(
        ValueError,
        match=r"code_virtual_no_read\.yaml:17: Webots input binding 'nearest' must "
        r"define a read method",
    ):
        transformer.transform(system)
