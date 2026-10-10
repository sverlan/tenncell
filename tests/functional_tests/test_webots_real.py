"""Opt-in contract: a generated controller runs in real Webots.

Set ``NNC_WEBOTS`` to the Webots executable (on Windows
``<Webots>/msys64/mingw64/bin/webots.exe``, which waits for the simulation) to
run it. The test copies the fixture world of
``tests/fixtures/transformers/webots/world/``, generates the controller of
``sensor_motor_csv.yaml`` into it and runs Webots headless (``--batch
--mode=fast --no-rendering``); a supervisor quits after a few steps. Webots
starts controllers with the ``python`` found on ``PATH``.
"""

import csv
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from nnc.cli_transform import _parse_webots_configs
from nnc.model.system import NncSystem
from nnc.transformers import WebotsTransformer

WEBOTS_FIXTURES = (
    Path(__file__).resolve().parents[1] / "fixtures" / "transformers" / "webots"
)
WEBOTS = os.environ.get("NNC_WEBOTS")
# STEPS of world/controllers/quitter/quitter.py. The robot's controller gets
# that many steps, or one more when it runs before the quit takes effect (it
# varies between runs); a controller that crashed would log fewer.
QUIT_STEPS = 5
STEP_COUNTS = (QUIT_STEPS, QUIT_STEPS + 1)

pytestmark = pytest.mark.skipif(
    not WEBOTS or not Path(WEBOTS).is_file(),
    reason="set NNC_WEBOTS to the Webots executable to run controllers in Webots",
)


def _run_in_webots(model: Path, tmp_path: Path) -> Path:
    """Generate the controller of ``model`` into the fixture world's
    ``sensor_motor`` controller slot, run Webots and return the controller
    directory."""
    project = tmp_path / "project"
    shutil.copytree(WEBOTS_FIXTURES / "world", project)
    cache: dict = {}
    system = NncSystem.from_yaml(str(model), _raw_data_cache=cache)
    transformer = WebotsTransformer()
    transformer.set_webots_configs(_parse_webots_configs([system], cache))
    controller_dir = project / "controllers" / "sensor_motor"
    controller_dir.mkdir()
    (controller_dir / "sensor_motor.py").write_text(
        transformer.transform(system), encoding="utf-8"
    )

    assert WEBOTS is not None
    run = subprocess.run(
        [
            WEBOTS,
            "--batch",
            "--mode=fast",
            "--no-rendering",
            "--minimize",
            "--stdout",
            "--stderr",
            str(project / "worlds" / "runtime.wbt"),
        ],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    return controller_dir


def _rows(path: Path) -> list[list[str]]:
    assert path.is_file(), path
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.reader(handle))


def test_generated_controller_runs_in_webots(tmp_path):
    model = WEBOTS_FIXTURES / "input" / "sensor_motor_csv.yaml"

    rows = _rows(_run_in_webots(model, tmp_path) / "sensor_motor.csv")

    assert rows[0] == ["_step", "_time", "distance", "speed"]
    # The initial row, then one row per step until the supervisor quits.
    steps = len(rows) - 2
    assert steps in STEP_COUNTS, rows
    # Webots' time after k steps of 32 ms, the input the step received (the
    # sensor reads 1000: nothing in range) and the model's speed.
    reference = NncSystem.from_yaml(str(model))
    expected = [[0, 0.0, 0.0, 0.0]]
    for step in range(1, steps + 1):
        reference.step({"distance": 1000.0})
        variables = reference.get_variables()
        expected.append([step, step * 0.032, 1000.0, float(variables["speed"])])
    logged = [[int(r[0]), *map(float, r[1:])] for r in rows[1:]]
    assert [row[:1] + row[2:] for row in logged] == [
        row[:1] + row[2:] for row in expected
    ]
    assert [row[1] for row in logged] == pytest.approx([row[1] for row in expected])
    assert expected[-1][3] == 1.0


def test_pasted_code_runs_in_webots(tmp_path):
    # code_points.yaml uses the world's devices; before_step scales the
    # sensor's 1000 by 0.001, so the model's speed is 1.0 on every step.
    model = WEBOTS_FIXTURES / "input" / "code_points.yaml"

    rows = _rows(_run_in_webots(model, tmp_path) / "code_points.csv")

    assert rows[0] == ["speed"]
    assert len(rows) - 1 in STEP_COUNTS, rows
    assert rows[1:] == [["1.0"]] * (len(rows) - 1)


def test_virtual_devices_work_in_webots(tmp_path):
    # code_virtual.yaml: the input comes from setup's object around the real
    # sensor (1000 * 0.001), the output goes to setup's recorder.
    model = WEBOTS_FIXTURES / "input" / "code_virtual.yaml"

    controller_dir = _run_in_webots(model, tmp_path)

    init, *echoed = (controller_dir / "echo.txt").read_text(encoding="utf-8").split()
    assert init == "-1"  # the init write, through the recorder
    assert len(echoed) in STEP_COUNTS, echoed
    assert echoed == ["1.0"] * len(echoed)


def test_methods_added_in_setup_work_in_webots(tmp_path):
    # code_patch.yaml: the init write (park), the scaled read and the LED's
    # int write go through methods added in setup; a missing method, or a
    # float given to LED.set, would end the controller at once.
    model = WEBOTS_FIXTURES / "input" / "code_patch.yaml"

    rows = _rows(_run_in_webots(model, tmp_path) / "code_patch.csv")

    assert rows[0] == ["speed", "led_on"]
    assert len(rows) - 1 in STEP_COUNTS, rows
    assert rows[1:] == [["1.0", "1.0"]] * (len(rows) - 1)
