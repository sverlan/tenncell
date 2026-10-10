"""In-process Webots simulator for running generated controllers in tests.

A test describes the robot's devices, runs the controller file in-process
and checks the recorded results:

    world = {"distance_sensor": DistanceSensor([1500.0]), "wheel": RotationalMotor()}
    result = run_controller(path, world, steps=2, monkeypatch=monkeypatch)

The controller's ``from controller import Robot`` gets this module's
``Robot`` (``sys.modules["controller"]`` is set through ``monkeypatch`` and
restored after the test). The file is loaded with ``importlib`` and its
``main()`` called; it runs in the current directory (tests ``chdir`` to their
``tmp_path``). Devices follow the Webots API (R2025a) where tests depend on
it: ``getDevice`` returns ``None`` with a warning for an unknown name, a
sensor read before ``enable`` returns NaN with a warning (what R2025a does;
Webots documents the value as undefined), and ``LED.set`` rejects floats as
Webots does through ctypes.
"""

from __future__ import annotations

import builtins
import contextlib
import ctypes
import importlib.util
import io
import math
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Simulation:
    """What happened during one run."""

    steps: int
    events: list[tuple] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    time_ms: int = 0
    module: types.ModuleType | None = None
    # Files the controller opened and had not closed when the run ended
    # (the simulator then closes them, as a process exit would).
    unclosed: list[str] = field(default_factory=list)


class Device:
    """A Webots device of the simulated robot."""

    def __init__(self) -> None:
        self.name = ""
        self._sim: Simulation | None = None

    def _record(self, *event) -> None:
        assert self._sim is not None
        self._sim.events.append(event)


class DistanceSensor(Device):
    """A sensor whose reads return ``values`` in turn (the last one repeats)."""

    def __init__(self, values: list[float]) -> None:
        super().__init__()
        self.values = list(values)
        self.enabled = False
        self._reads = 0

    def enable(self, timestep: int) -> None:
        self.enabled = True
        self._record("enable", self.name, timestep)

    def getValue(self) -> float:
        if not self.enabled:
            assert self._sim is not None
            self._sim.warnings.append(
                f"getValue() called for the disabled device {self.name}"
            )
            value = math.nan
        else:
            value = self.values[min(self._reads, len(self.values) - 1)]
            self._reads += 1
        self._record("getValue", self.name, value)
        return value


class RotationalMotor(Device):
    """A motor recording its velocity and position commands."""

    def setVelocity(self, value: float) -> None:
        self._record("setVelocity", self.name, value)

    def setPosition(self, value: float) -> None:
        self._record("setPosition", self.name, value)


class LED(Device):
    """An LED; like Webots, ``set`` takes an int (or bool), not a float."""

    def set(self, value: int) -> None:
        if not isinstance(value, int):
            raise ctypes.ArgumentError(
                "argument 2: Don't know how to convert parameter 2"
            )
        self._record("set", self.name, value)


class _Lines(io.TextIOBase):
    """stdout replacement recording each printed line as a ("print", line) event."""

    def __init__(self, sim: Simulation) -> None:
        self._sim = sim
        self._pending = ""

    def write(self, text: str) -> int:
        self._pending += text
        *lines, self._pending = self._pending.split("\n")
        for line in lines:
            self._sim.events.append(("print", line))
        return len(text)

    def finish(self) -> None:
        """Record text printed without a final newline."""
        if self._pending:
            self._sim.events.append(("print", self._pending))
            self._pending = ""


def _api(sim: Simulation, world: dict[str, Device]) -> types.ModuleType:
    """The ``controller`` module the generated code imports."""

    class Robot:
        def __init__(self) -> None:
            sim.events.append(("robot",))

        def getBasicTimeStep(self) -> float:
            return 16.0

        def getDevice(self, name: str) -> Device | None:
            if name not in world:
                sim.warnings.append(f'Device "{name}" was not found on robot')
                return None
            sim.events.append(("getDevice", name))
            return world[name]

        def getTime(self) -> float:
            return sim.time_ms / 1000.0

        def step(self, timestep: int) -> int:
            if sim.steps == 0:
                sim.events.append(("step_end", timestep))
                return -1
            sim.steps -= 1
            sim.time_ms += timestep
            sim.events.append(("step", timestep))
            return 0

    module = types.ModuleType("controller")
    module.Robot = Robot  # type: ignore[attr-defined]
    return module


def run_controller(
    path: Path,
    world: dict[str, Device],
    steps: int,
    monkeypatch,
    simulation: Simulation | None = None,
) -> Simulation:
    """Run the controller file ``path`` for ``steps`` steps in ``world``.

    Like a script started by Webots: the controller module is registered in
    ``sys.modules`` and its folder is first on ``sys.path`` (both restored
    by ``monkeypatch``), and files it opened are closed when the run ends,
    as at process exit. Exceptions of the controller propagate; pass
    ``simulation`` to inspect the recorded run after one. Returns the
    recorded run, with the loaded controller module.
    """
    sim = simulation if simulation is not None else Simulation(steps=steps)
    sim.steps = steps
    for name, device in world.items():
        device.name = name
        device._sim = sim
    monkeypatch.setitem(sys.modules, "controller", _api(sim, world))
    monkeypatch.syspath_prepend(str(path.parent))
    spec = importlib.util.spec_from_file_location("controller_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "controller_under_test", module)
    sim.module = module
    opened: list = []
    real_open = builtins.open

    def tracking_open(*args, **kwargs):
        handle = real_open(*args, **kwargs)
        opened.append(handle)
        return handle

    monkeypatch.setattr(builtins, "open", tracking_open)
    lines = _Lines(sim)
    try:
        with contextlib.redirect_stdout(lines):
            spec.loader.exec_module(module)
            module.main()
    finally:
        lines.finish()
        monkeypatch.setattr(builtins, "open", real_open)
        sim.unclosed = [handle.name for handle in opened if not handle.closed]
        for handle in opened:
            handle.close()
    return sim
