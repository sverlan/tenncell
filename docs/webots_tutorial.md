# Webots Controllers from TENNCell Models

This tutorial shows how to drive a Webots robot with a TENNCell model:
first with plain bindings, then with your own Python code pasted into the
controller, and finally with virtual devices that combine several sensors.
The exact rules are in `rules.md`, section "Webots Backend".

`nnc-gen -t webots` writes one Python controller file. It does not create
Webots worlds or robots; it only generates the glue between the robot's
devices and the model.

## 1. A controller with plain bindings

A binding connects a model variable to a Webots device: inputs are read from
a device each step, outputs are written to one.

```yaml
cells:
  - id: 1
    contents:
      - distance = 0
      - speed = 0
      - position = 0
    input: [distance]
    output: [speed]
rules:
  - speed * 0 -> speed              # clear the previous speed
  - distance * 0.001 -> speed

webots:
  timestep: 64                      # optional; default: the world's basic time step
  bindings:
    distance:
      device: ps0                   # the device name in the robot
      read_method: getValue
    speed:
      device: left wheel motor
      write_method: setVelocity
    position:
      device: left wheel motor
      write_method: setPosition
  init:
    position: inf                   # written once: velocity mode for the motor
  csv:
    file: run.csv
    variables: [speed]
    include_step: true
```

Every model input needs a binding with a `read_method`, every output one with
a `write_method`. `init` writes values once, before the loop; here it puts the
motor in velocity mode. `csv` logs variables after each step.

Generate the controller and install it in your Webots project:

```text
nnc-gen model.yaml -t webots -o out
```

Copy `out/model.py` to `controllers/<name>/<name>.py` in the Webots project,
and set the robot's `controller` field to `<name>`. The file name, the folder
and the field must match; `webots.controller_name` only names the controller
in comments.

What the controller does, in order:

1. creates the robot and gets one device per binding (`robot.getDevice`);
2. enables the input devices (`enable(timestep)`), writes the `init` values,
   opens the CSV log;
3. loops `while robot.step(timestep) != -1`: reads the inputs, runs one model
   step, logs the CSV row, writes the outputs;
4. closes the CSV log when Webots stops the controller, also if an error
   ends it.

Reads see the world after the physics step; writes take effect at the next
one. A CSV row holds the input the step received and the other variables
*after* the step, as `nnc-verify` rows do: an input that a rule consumes
(as `distance` above) still logs its value. Properties can be checked on a run
with `nnc-verify model.yaml --trace run.csv` when the CSV lists the variables
the properties use.

## 2. Pasting your own code

Unit conversion, filtering, extra devices or logging need a little Python.
`webots.code` pastes your code into the controller at five fixed points:

| Point | Runs |
|---|---|
| `module` | once, at the top of the file: imports, helper functions, constants |
| `setup` | once, right after the devices are created, before `enable`, `init` and the loop |
| `before_step` | each step, after the inputs are read, before the model step |
| `after_step` | each step, after the model step and the CSV row, before the outputs are written |
| `shutdown` | once, after the loop, also after an error |

Each point takes a YAML block (`|` keeps the lines as written) or
`{file: PATH}`, a file relative to the YAML file. `nnc-gen` pastes the code
between marker comments; it never runs or imports it. `module` code sits at
the top level of the file: it defines things (imports, functions, classes)
that the other points use, but it cannot see the controller's objects. The
other points run inside the controller and may use `robot`, `timestep`,
`devices` (by binding variable) and `nnc` (the model), plus what `module`
defines; `before_step` also sees `inputs` (the values the model receives,
which you may change) and `after_step` sees `variables` (the values after the
step).

```yaml
webots:
  code:
    module: |
      import math
    before_step: |
      # Readings in millimetres; the model works in metres.
      inputs['distance'] = inputs['distance'] / 1000.0
    after_step: |
      if variables['speed'] > 5:
          print('fast at', robot.getTime())
```

### Adding a method to a device

A binding calls one method: a `read_method` without arguments (its result is
converted with `float`), a `write_method` with the model's value. When a
device needs something else, `setup` can add a method to the device object,
and the binding names it. A Webots LED, for example, takes an integer, while the model gives
floats:

```yaml
webots:
  bindings:
    alarm:
      device: led0
      write_method: set_int        # added in setup
  code:
    setup: |
      led = devices['alarm']
      led.set_int = lambda value: led.set(int(value))
```

Because `setup` runs before `enable`, the `init` writes and the loop, added
methods work for all of them. `read_method` and `write_method` should be
method names: put expressions in such a method, not in the YAML. An
expression in the YAML still works, but `nnc-gen` warns, since it pastes the
text unchecked.

## 3. Virtual devices

Some model values are not one device: the closest obstacle among several
sensors, a value computed from a camera image, an output recorded to a file.
Leave `device` out of the binding, and let `setup` provide the device: any
Python object with the binding's method.

`examples/webots/e_puck_virtual_sensors/` does this for the e-puck. The model
reacts to the closest obstacle on each side; each side combines three
proximity sensors (left `ps5`, `ps6`, `ps7`; right `ps0`, `ps1`, `ps2`):

```yaml
webots:
  bindings:
    left_obstacle:               # no device: virtual
      read_method: getValue
    right_obstacle:
      read_method: getValue
  code:
    module:
      file: code/devices.py      # defines Combined and add_clamped_velocity
    setup: |
      devices['left_obstacle'] = Combined(robot, ['ps5', 'ps6', 'ps7'], timestep)
      devices['right_obstacle'] = Combined(robot, ['ps0', 'ps1', 'ps2'], timestep)
```

`Combined` (in `code/devices.py`) gets and enables the real sensors, and its
`getValue` returns the largest reading: e-puck proximity values grow as an
obstacle comes closer, so the maximum is the closest obstacle on that side
(use `min` for sensors that report a distance). The controller reads
`devices['left_obstacle'].getValue()` every step, like any other input. The
same example gives the wheels a clamping `set_speed` method, so the model can
compute any speed while the motors get at most the e-puck's 6.28 rad/s.

The two cases stay apart:

- a real device (`device: ps0`) is looked up with `robot.getDevice`; a wrong
  name gets Webots' own "Device ... was not found" warning;
- a virtual device (no `device`) is not looked up; `setup` must set
  `devices['x']`. Without any `setup` code, `nnc-gen` reports an error; if
  `setup` forgets one, the controller stops right after `setup` with
  `Webots binding 'x' has no device: webots.code.setup must set devices['x']`.

## 4. Common mistakes

- **Rules add to their targets.** A rule `expr -> speed` adds to `speed`
  unless something consumes it; clear it each step with `speed * 0 -> speed`.
- **Wrong method for the device.** The controller calls exactly the method
  you name, with a float; a Webots LED has `set` (an integer), not
  `setValue`. Use an added method (section 2) to convert.
- **Device name typos.** Webots prints "Device ... was not found" and the
  controller fails at the first read or write; check the robot's device
  names in the Webots scene tree.
- **Internal variables in the CSV log.** Apart from inputs, values are
  logged after the step: a variable that a rule consumes and nothing
  refills logs 0.

## 5. Running without the Webots window

Webots can run a world headless, for example to log a run:

```text
webots --batch --mode=fast --no-rendering --minimize worlds/my_world.wbt
```

(On Windows, `webots.exe` in `<Webots>\msys64\mingw64\bin` waits for the
simulation to end.) The simulation runs until a supervisor robot calls
`simulationQuit(0)`, for example after a fixed number of steps.
