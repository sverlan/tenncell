"""Contract: generated Webots controllers run as documented (simulated Webots).

Each test generates a controller from a fixture under
``tests/fixtures/transformers/webots/input/`` and runs it in-process with the
small Webots simulator of ``webots_sim.py``: the test describes the robot's
devices, and checks the recorded calls (in order, with printed lines), the
warnings and the files the controller wrote. Written values must be those of
the model run on the same inputs.
"""

import csv
import ctypes
import math
from pathlib import Path

import pytest
from webots_sim import LED, DistanceSensor, RotationalMotor, Simulation, run_controller

from nnc.cli_transform import _parse_webots_configs
from nnc.model.system import NncSystem
from nnc.transformers import WebotsTransformer

INPUT = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "transformers"
    / "webots"
    / "input"
)


def _run(model: str, world: dict, steps: int, tmp_path: Path, monkeypatch, sim=None):
    """Generate the controller of ``model`` and run it in ``tmp_path``."""
    cache: dict = {}
    system = NncSystem.from_yaml(str(INPUT / model), _raw_data_cache=cache)
    transformer = WebotsTransformer()
    transformer.set_webots_configs(_parse_webots_configs([system], cache))
    controller = tmp_path / "controller_under_test.py"
    controller.write_text(transformer.transform(system), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return run_controller(controller, world, steps, monkeypatch, sim)


def _model_outputs(model: str, inputs: list[dict]) -> list[dict]:
    """Outputs of the model itself after each step."""
    system = NncSystem.from_yaml(str(INPUT / model))
    return [system.step(record) for record in inputs]


def _rows(path: Path) -> list[list[str]]:
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.reader(handle))


def test_reads_steps_and_writes_follow_the_documented_order(tmp_path, monkeypatch):
    world = {
        "distance_sensor": DistanceSensor([1000.0, 2500.0, 400.0]),
        "wheel": RotationalMotor(),
    }

    sim = _run("sensor_motor_csv.yaml", world, 3, tmp_path, monkeypatch)
    outputs = _model_outputs(
        "sensor_motor_csv.yaml",
        [{"distance": 1000.0}, {"distance": 2500.0}, {"distance": 400.0}],
    )

    assert sim.events == [
        ("robot",),
        ("getDevice", "distance_sensor"),
        ("getDevice", "wheel"),  # one call per binding: speed and position
        ("getDevice", "wheel"),
        ("enable", "distance_sensor", 32),
        ("setPosition", "wheel", math.inf),  # the init write, once
        # robot.step comes first: reads see the state after the physics step,
        # writes take effect at the next one.
        ("step", 32),
        ("getValue", "distance_sensor", 1000.0),
        ("setVelocity", "wheel", outputs[0]["speed"]),
        ("step", 32),
        ("getValue", "distance_sensor", 2500.0),
        ("setVelocity", "wheel", outputs[1]["speed"]),
        ("step", 32),
        ("getValue", "distance_sensor", 400.0),
        ("setVelocity", "wheel", outputs[2]["speed"]),
        ("step_end", 32),
    ]
    assert sim.warnings == []


def test_csv_logs_received_inputs_and_post_step_variables(tmp_path, monkeypatch):
    world = {
        "distance_sensor": DistanceSensor([3000.0, 5000.0]),
        "wheel": RotationalMotor(),
    }

    _run("sensor_motor_csv.yaml", world, 2, tmp_path, monkeypatch)
    system = NncSystem.from_yaml(str(INPUT / "sensor_motor_csv.yaml"))
    rows = [(float(system.get_variables()["distance"]), system.get_variables())]
    for value in (3000.0, 5000.0):
        system.step({"distance": value})
        rows.append((value, system.get_variables()))

    logged = _rows(tmp_path / "sensor_motor.csv")
    assert logged[0] == ["_step", "_time", "distance", "speed"]
    # Row k: the simulation time after k steps of 32 ms, the input step k
    # received (as nnc-verify --inputs rows: the rule `distance * 0.001 ->
    # speed` consumes it, so its post-step value would be 0), and the other
    # variables after step k. Row 0 holds the initial values. The controller
    # computes in floats, the simulator may keep ints.
    assert [[int(r[0]), *map(float, r[1:])] for r in logged[1:]] == [
        [k, k * 0.032, received, float(row["speed"])]
        for k, (received, row) in enumerate(rows)
    ]
    assert float(rows[1][1]["distance"]) == 0.0  # the consumed post-step value


def test_two_bindings_of_one_device_share_it(tmp_path, monkeypatch):
    world = {"left wheel": RotationalMotor(), "right wheel": RotationalMotor()}

    sim = _run("motor_velocity.yaml", world, 2, tmp_path, monkeypatch)
    outputs = _model_outputs("motor_velocity.yaml", [{}, {}])

    assert sim.events[:7] == [
        ("robot",),
        ("getDevice", "left wheel"),
        ("getDevice", "right wheel"),
        ("getDevice", "left wheel"),
        ("getDevice", "right wheel"),
        ("setPosition", "left wheel", math.inf),
        ("setPosition", "right wheel", math.inf),
    ]
    assert sim.events[7:] == [
        ("step", 64),
        ("setVelocity", "left wheel", outputs[0]["left_speed"]),
        ("setVelocity", "right wheel", outputs[0]["right_speed"]),
        ("step", 64),
        ("setVelocity", "left wheel", outputs[1]["left_speed"]),
        ("setVelocity", "right wheel", outputs[1]["right_speed"]),
        ("step_end", 64),
    ]


def test_an_unknown_device_name_warns_and_fails_at_the_first_read(
    tmp_path, monkeypatch
):
    # The world has no distance_sensor: getDevice returns None with Webots'
    # warning, enable is skipped (hasattr guard), and the first read fails.
    world = {"wheel": RotationalMotor()}
    sim = Simulation(steps=2)

    with pytest.raises(
        AttributeError, match="'NoneType' object has no attribute 'getValue'"
    ):
        _run("sensor_motor_csv.yaml", world, 2, tmp_path, monkeypatch, sim)

    assert sim.warnings == ['Device "distance_sensor" was not found on robot']
    assert sim.events == [
        ("robot",),
        ("getDevice", "wheel"),
        ("getDevice", "wheel"),
        ("setPosition", "wheel", math.inf),
        ("step", 32),
    ]
    # The controller itself closed its CSV log (try/finally), before the
    # error went on.
    assert sim.unclosed == []


def test_shutdown_code_runs_after_an_error(tmp_path, monkeypatch):
    # code_points.yaml in a world without the wheel: the first write fails;
    # the finally block still closes the CSV and runs the shutdown code.
    world = {"distance_sensor": DistanceSensor([1500.0])}
    sim = Simulation(steps=2)

    with pytest.raises(
        AttributeError, match="'NoneType' object has no attribute 'setVelocity'"
    ):
        _run("code_points.yaml", world, 2, tmp_path, monkeypatch, sim)

    assert sim.events[-1] == ("print", "shutdown")
    assert sim.unclosed == []
    assert _rows(tmp_path / "code_points.csv") == [["speed"], ["1.5"]]


def test_shutdown_code_runs_after_an_error_without_a_csv_log(tmp_path, monkeypatch):
    # code_shutdown.yaml: shutdown code and no CSV (the finally block starts
    # with pass); the world has no wheel, so the first write fails.
    world = {"distance_sensor": DistanceSensor([1.0])}
    sim = Simulation(steps=2)

    with pytest.raises(
        AttributeError, match="'NoneType' object has no attribute 'setVelocity'"
    ):
        _run("code_shutdown.yaml", world, 2, tmp_path, monkeypatch, sim)

    assert sim.events[-1] == ("print", "stopped")


def test_the_simulator_reports_files_a_controller_leaves_open(tmp_path, monkeypatch):
    controller = tmp_path / "leaky.py"
    controller.write_text(
        "def main():\n    open('left_open.txt', 'w')\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    sim = run_controller(controller, {}, 0, monkeypatch)

    assert sim.unclosed == ["left_open.txt"]


def test_a_method_the_device_lacks_fails_at_the_first_write(tmp_path, monkeypatch):
    # sensor_led.yaml writes the LED with setValue; a Webots LED has only set.
    world = {"distance_sensor": DistanceSensor([1.0]), "led": LED()}

    with pytest.raises(
        AttributeError, match="'LED' object has no attribute 'setValue'"
    ):
        _run("sensor_led.yaml", world, 2, tmp_path, monkeypatch)


def test_the_simulated_led_rejects_floats_like_webots():
    with pytest.raises(ctypes.ArgumentError):
        LED().set(1.0)


def test_a_disabled_sensor_reads_nan_with_a_warning(tmp_path, monkeypatch):
    # Like Webots: a sensor read before enable gives NaN and a warning.
    controller = tmp_path / "reader.py"
    controller.write_text(
        "from controller import Robot\n\n"
        "def main():\n"
        "    robot = Robot()\n"
        "    print(robot.getDevice('s').getValue())\n",
        encoding="utf-8",
    )

    sim = run_controller(controller, {"s": DistanceSensor([5.0])}, 0, monkeypatch)

    assert sim.events[-1] == ("print", "nan")
    assert sim.warnings == ["getValue() called for the disabled device s"]


def test_controllers_run_like_scripts(tmp_path, monkeypatch):
    # As in Webots: module-level dataclasses work (they look their module up
    # in sys.modules), helper files next to the controller can be imported,
    # and printed text without a final newline is kept.
    (tmp_path / "helper.py").write_text("FACTOR = 3\n", encoding="utf-8")
    controller = tmp_path / "script.py"
    controller.write_text(
        "from __future__ import annotations\n"
        "from dataclasses import dataclass\n"
        "from typing import ClassVar\n"
        "from helper import FACTOR\n\n"
        "@dataclass\n"
        "class Gain:\n"
        "    unit: ClassVar[str] = 'x'\n"
        "    value: int\n\n"
        "def main():\n"
        "    print(Gain(FACTOR).value, end='')\n",
        encoding="utf-8",
    )

    sim = run_controller(controller, {}, 0, monkeypatch)

    assert sim.events == [("print", "3")]


def test_an_expression_method_still_works(tmp_path, monkeypatch):
    # expression_method.yaml: an expression in read_method, accepted
    # with a warning (see the parser tests): the reading reaches the model
    # scaled by 0.001.
    world = {"distance_sensor": DistanceSensor([1500.0]), "wheel": RotationalMotor()}

    sim = _run("expression_method.yaml", world, 1, tmp_path, monkeypatch)

    assert ("setVelocity", "wheel", 1.5) in sim.events


def test_user_code_runs_at_its_insertion_points(tmp_path, monkeypatch):
    # code_points.yaml prints a line at each insertion point; before_step
    # scales the reading by 0.001 before the model sees it.
    world = {
        "distance_sensor": DistanceSensor([1500.0, 500.0]),
        "wheel": RotationalMotor(),
    }

    sim = _run("code_points.yaml", world, 2, tmp_path, monkeypatch)

    assert sim.events == [
        ("robot",),
        ("getDevice", "distance_sensor"),
        ("getDevice", "wheel"),
        ("print", "setup 32"),
        ("enable", "distance_sensor", 32),
        ("step", 32),
        ("getValue", "distance_sensor", 1500.0),
        ("print", "before_step 1500.0"),
        ("print", "after_step 1.5"),
        ("print", "fast"),
        ("setVelocity", "wheel", 1.5),
        ("step", 32),
        ("getValue", "distance_sensor", 500.0),
        ("print", "before_step 500.0"),
        ("print", "after_step 0.5"),
        ("setVelocity", "wheel", 0.5),
        ("step_end", 32),
        ("print", "shutdown"),
    ]
    # The CSV logs the model's values, computed from the modified inputs.
    assert _rows(tmp_path / "code_points.csv") == [["speed"], ["1.5"], ["0.5"]]
    # Module code is part of the controller module.
    assert sim.module is not None and sim.module.scaled(1000.0) == 1.0


def test_methods_added_in_setup_serve_reads_init_and_writes(tmp_path, monkeypatch):
    # code_patch.yaml: setup adds read_scaled, park and set_int to the
    # devices, and the bindings and the init write call them.
    world = {
        "distance_sensor": DistanceSensor([1500.0, 500.0]),
        "wheel": RotationalMotor(),
        "led": LED(),
    }

    sim = _run("code_patch.yaml", world, 2, tmp_path, monkeypatch)

    assert sim.events == [
        ("robot",),
        ("getDevice", "distance_sensor"),
        ("getDevice", "wheel"),
        ("getDevice", "wheel"),
        ("getDevice", "led"),
        ("enable", "distance_sensor", 32),
        ("setPosition", "wheel", math.inf),  # init through park
        ("step", 32),
        ("getValue", "distance_sensor", 1500.0),  # read_scaled: 1.5 to the model
        ("setVelocity", "wheel", 1.5),
        ("set", "led", 1),  # set_int: the LED accepts it (a float would raise)
        ("step", 32),
        ("getValue", "distance_sensor", 500.0),
        ("setVelocity", "wheel", 0.5),
        ("set", "led", 1),
        ("step_end", 32),
    ]


def test_virtual_devices_are_provided_by_setup_code(tmp_path, monkeypatch):
    # code_virtual.yaml: no getDevice or enable for the bindings without a
    # device; setup's objects read a real sensor and record the output.
    world = {"distance_sensor": DistanceSensor([1500.0, 500.0])}

    sim = _run("code_virtual.yaml", world, 2, tmp_path, monkeypatch)

    assert sim.events == [
        ("robot",),
        ("getDevice", "distance_sensor"),  # by the setup code
        ("enable", "distance_sensor", 32),  # by the setup code
        ("step", 32),
        ("getValue", "distance_sensor", 1500.0),
        ("step", 32),
        ("getValue", "distance_sensor", 500.0),
        ("step_end", 32),
    ]
    # The init write (-1) goes through the recorder, then one value per step.
    assert (tmp_path / "echo.txt").read_text(encoding="utf-8").split() == [
        "-1",
        "1.5",
        "0.5",
    ]


def test_a_virtual_device_left_unset_stops_the_controller_before_the_loop(
    tmp_path, monkeypatch
):
    world = {"wheel": RotationalMotor()}

    with pytest.raises(
        RuntimeError,
        match=r"Webots binding 'nearest' has no device: webots\.code\.setup "
        r"must set devices\['nearest'\]",
    ):
        _run("code_virtual_missing.yaml", world, 2, tmp_path, monkeypatch)
