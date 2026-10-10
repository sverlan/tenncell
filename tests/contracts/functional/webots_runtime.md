# Webots Runtime Contract

Generated controllers are run, not only compared with golden text.

## Simulated Webots (always runs)

`test_webots_runtime.py` generates a controller from a fixture under
`tests/fixtures/transformers/webots/input/` and runs it in-process with the
simulator of `tests/functional_tests/webots_sim.py`: the controller file is
loaded with `importlib` and its `main()` called, and its `from controller
import Robot` gets the simulator (`sys.modules["controller"]`, set through
pytest's `monkeypatch`). As for a script started by Webots, the controller
module is registered in `sys.modules`, its folder is first on `sys.path`
(both restored after the test), and files it opened are closed when the run
ends, also after an exception. Each test describes the robot's devices; the
simulator records the calls in order (with printed lines, also without a
final newline), the warnings and the files written, and a test can pass its
own `Simulation` to inspect a run that raised. Its devices follow Webots
R2025a where the tests depend on it: an unknown name gives `None` and a
warning, a sensor read before `enable` gives NaN and a warning (Webots
documents the value as undefined), and `LED.set` rejects floats.

- `sensor_motor_csv.yaml`: device creation (one `getDevice` per binding),
  sensor `enable`, the `init` write once, then per step `robot.step`, the read
  and the write, in that order; written values are the model's outputs. The
  CSV log has the header, the initial row and one row per step with the
  simulation time, the input the step received (also when a rule consumed
  it) and the other variables after the step.
- `motor_velocity.yaml`: two bindings of one device share it; `init` values
  are written once before the loop; outputs are written every step.
- Failures as in Webots: a device name missing from the robot gives Webots'
  warning and fails at the first read (`None`), with the CSV file closed
  afterwards; `sensor_led.yaml`'s `setValue` fails on a real LED, which only
  has `set`.
- Script semantics: a module-level dataclass and an import of a helper file
  next to the controller work, as in Webots.
- Cleanup after an error: when a read or write fails, the controller itself
  closes its CSV log (the simulator reports no file left open) and runs the
  `shutdown` code before the error goes on, with a CSV log (`code_points.yaml`)
  and without one (`code_shutdown.yaml`); the simulator reports files a
  controller leaves open.
- `code_points.yaml`: user code runs at its insertion points (`setup`
  right after the devices, before `enable`; `before_step` after the reads;
  `after_step` before the writes; `shutdown` after the loop), as its printed
  lines show; an input changed in `before_step` is what the model receives,
  as the writes and the CSV show.
- `code_virtual.yaml`: bindings without `device` get no `getDevice` or
  `enable`; the objects `setup` provides read a real sensor and record the
  output. `code_virtual_missing.yaml`: `setup` leaves the virtual device
  unset, and the controller stops before the loop with an error naming the
  binding.
- `code_patch.yaml`: methods added to the devices in `setup` serve the read
  (scaled), the `init` write and the LED write, which receives an `int`.

## Real Webots (opt-in)

`test_webots_real.py` runs only when `NNC_WEBOTS` points to the Webots
executable (on Windows `<Webots>/msys64/mingw64/bin/webots.exe`). It copies
the world of `tests/fixtures/transformers/webots/world/`, generates the
controller of `sensor_motor_csv.yaml` into it and runs Webots headless; a
supervisor quits after five steps.

- Webots exits with status 0 and the CSV has the initial row plus one row
  per step: five or six, as the robot's controller may run once more before
  the supervisor's quit takes effect (a crash would end it early); the motor
  is put in velocity mode by the `init` write, and the CSV rows equal the
  model run on the sensor's reading (1000, nothing in range).
- `code_patch.yaml` in the same world (which has an LED): the added methods
  work in Webots, including `LED.set` with an int (a float would stop the
  controller).
- `code_virtual.yaml` in the same world: the virtual input and output work
  in Webots.
- `code_points.yaml` in the same world: the pasted code runs in Webots
  (`before_step` scales the sensor's 1000 by 0.001, so every CSV row is
  `1.0`).
