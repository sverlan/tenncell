# TENNCell

TENNCell stands for Transformation and Execution of Numerical Networks of
Cells. It is a model related to numerical P systems that generalizes many of
their variants. This package parses and simulates TENNCell systems and exports
them to generated code.

## Current Capabilities
- Python simulation of standalone and import-composed TENNCell YAML systems
- Python source export through `nnc-gen -t python`, including import-composed systems as a single generated file
- Verilog/SystemVerilog export through `nnc-gen -t verilog`
- Webots Python controller export through `nnc-gen -t webots`
- Optional import/composition metadata for optimized Verilog generation

## Installation

Use one of these depending on how you want to consume the package:

- `pip install tenncell` if you want the package and commands in your current Python environment
- `pipx install tenncell` if you want an isolated command-line installation
- `pdm install --dev` if you are developing from a clone of this repository

## Quick Start
If you want to try the package immediately, start with one of the examples:

- simulate a standalone TENNCell file: `nnc-sim examples/simple/example1.yaml`
- generate Verilog from a typed FPGA example: `nnc-gen examples/fpga/blink_uart_typed/blink_uart_typed.yaml -t verilog`
- inspect the available commands and version: `nnc-sim --help`, `nnc-gen --help`, `nnc-sim --version`, and `nnc-gen --version`

The `python -m nnc` form invokes the simulator with the same defaults as `nnc-sim`.

## Simulation

TENNCell has two simulation modes:

### IO mode
- This is the default mode.
- It reads CSV input rows and writes CSV output rows.
- Use it when you want to process a stream of inputs and capture the produced outputs.

Example:
```powershell
nnc-sim examples/simple/example1.yaml input.csv output.csv
```

### Compute mode
- This mode does not consume CSV input.
- It runs the system for a fixed number of steps and prints the output state.
- Use it when you want a bounded run with no CSV input file.

Example:
```powershell
nnc-sim examples/simple/example1.yaml -c -s 10
```

The `--csv` flag only affects compute mode and makes the output CSV-formatted.
CSV output uses comma as the default delimiter. Use `--csv-delimiter` to change
the delimiter for both CSV input and output, and `--csv-precision` to format
numeric output values with a fixed number of decimal places. Compute-mode CSV
includes the initial state as step `0` by default; use `--csv-no-initial` to suppress
it. IO mode omits the initial row by default; use `--csv-include-initial` to emit
the state before the first input row without adding a `step` column.
Use `nnc-sim --version` to print the simulator version.

The simulator supports standalone TENNCell YAML and import-composed TENNCell systems.

## Transformers

Use `nnc-gen` to generate backend-specific outputs:

```powershell
nnc-gen <system_file.yaml> -t {python,verilog,webots} [options]
```

Options:
- `-o`, `--output-dir DIR`: output directory
- `--output-suffix SUFFIX`: suffix inserted before the generated file extension
- `--import-path DIR`: extra import search path, may be repeated
- `--import-paths LIST`: path-separated import search list
- `-v`, `--verbose`: verbose logging
- `--version`: print the `nnc-gen` version

Import resolution order:
1. relative to the importing YAML file
2. `--import-path` / `--import-paths` directories in the order provided

### Python backend
`nnc-gen -t python` generates a single Python source file for the selected TENNCell model.
It flattens import-composed systems into one generated file.
Use this backend when you want a Python artifact you can inspect, run, or integrate into a larger Python workflow.

Example:
```powershell
nnc-gen examples/composition/python_composed/python_composed_controller.yaml -t python
```

The generated file is a Python module. It exposes the TENNCell model as normal Python classes and methods, so you can import it into another script or run it directly as a generated artifact. If the source TENNCell system has inputs, the generated code uses the same CSV conventions as the simulator, including `--csv-delimiter`, `--csv-precision`, and `--csv-include-initial`; otherwise it can be stepped directly and supports `--csv-no-initial`. The generated main class exposes a `step` method for integration into a larger workflow.

### Webots backend
`nnc-gen -t webots` generates a Python controller for Webots.
The Webots YAML adds sensor and actuator metadata through `webots.bindings` and `webots.init`.
`webots.bindings` maps TENNCell variables to Webots devices and names the read or write method the controller should call.
`webots.init` sets initial device state for outputs or actuators that need a startup value.
Use this backend when you want TENNCell to drive a Webots robot or read its sensors.

Example:
```powershell
nnc-gen examples/webots/e_puck_pid/e_puck_pid.yaml -t webots
```

### Verilog backend
`nnc-gen -t verilog` generates SystemVerilog RTL.
The current form uses:
- `.sv` output files
- `` `default_nettype none`` throughout the generated module
- `always_comb` for next-state logic and `always_ff` for registered state
- module-local `localparam` aliases for fixed-point literals
- `verilog.real_encoding` as the module numeric contract
- `verilog.ports` for top-level port declarations and boundary typing
- `verilog.externals` for wiring external RTL modules through explicit connections

Verilog port entries may specify `kind`; it defaults to `logic` when omitted.
The `clock` and `reset` fields are scalar names for the generated boundary signals.
They are not TENNCell aliases, but external module connections may still wire to them
through `verilog.externals.connections`.

The simple UART-to-LED example below shows the overall shape without introducing
the more complex typed blink example.

## YAML Schema

A sample example looks like

```yaml
module:
  name: fir
  description: "3-tap FIR filter"
cells:
  - id: 1
    contents:
      - x=0
      - x1=0, x2=0
      - y=0
    input: [x]
    output: [y]
rules:
  - x -> x1
  - x1 -> x2
  - 0.2 * x + 0.5 * x1 + 0.3 * x2 -> y
  - 0 * y -> y
  - 0 * x1 -> x1
  - 0 * x2 -> x2
```

An important parameter is `module.zero_reset_mode`, which defaults to false. In this mode, if a variable is not used, it keeps its previous value, so it can accumulate between steps. When true, the variable values are reset to zero at each step, regardless of whether they are used or not. In particular, this simplifies Verilog code generation.


The system can have additional `verilog` and/or `webots` sections that contain instructions specific to these backends:

```yaml
module: controller
zero_reset_mode: true
...
verilog:
...
webots:
...
```

Additional YAML sugar is also supported:
- top-level `if` / `then` / `else` blocks
- recursive nested `if` blocks anywhere a rule list is allowed
- `fsm:` blocks with one or more FSMs per module

Example:
```yaml
fsm:
  - name: ctrl
    variable: ctrl_state
    initial: IDLE
    states:
      - IDLE:
          rules:
            - if: start > 0
              then: RUN -> ctrl_state
      - RUN:
          rules:
            - if: done > 0
              then: IDLE -> ctrl_state
```

Single-item sugar is accepted in branch bodies, so these are equivalent:
```yaml
then:
  - 1 -> y
```

```yaml
then: 1 -> y
```

`repeat` can be used inside core TENNCell lists to generate repeated contents or
rules. Ranges are inclusive, integer-only, and placeholders use `${i}`,
`${i+K}`, or `${i-K}`:

```yaml
cells:
  - id: 1
    contents:
      - repeat:
          var: i
          range: [0, 3]
          body:
            - x_${i} = ${i}

rules:
  - repeat:
      var: i
      range: [1, 3]
      body:
        - x_${i-1} + 1 -> x_${i}
```

In the first version, `repeat` is supported only in `cells[].contents`,
`cells[].input`, `cells[].output`, and top-level `rules`. See
`examples/simple/repeat.yaml` for a standalone example.

Qualified references supported by the parser:
- local variable: `x`
- imported TENNCell IO: `sensor0.level`
- Verilog port names are not part of TENNCell alias resolution

Constants may be literal numbers or load-time constant expressions. Expressions are evaluated in declaration order and may reference only previously declared constants:

```yaml
constants:
  A: 2 * 5
  B: 3 * A + 1
```

Aliases can be defined, that correspond to variable renaming. They are mostly used for imported modules:

```yaml
aliases:
  sensed: sensor0.level
```

### Imports vs Externals
- `imports:` composes TENNCell modules together.
- `verilog.externals` wraps external RTL modules and wires TENNCell variables to their ports.
- For import composition patterns, see `examples/composition/`.
- For external-module wiring examples, see `examples/fpga/`.

## Defaults

TENNCell YAML files without a module section are still supported:

```yaml
cells:
  - id: 1
    contents:
      - x = 0
      - y = 1
    input: [x]
    output: [y]

rules:
  - x + 1 -> y
```

If `module` is absent, the effective defaults are:
- module name: source filename stem
- `zero_reset_mode`: `false`

If `constants`, `aliases`, `imports`, `verilog.externals`, or `webots.bindings` are absent, they default to empty where the selected backend allows them.


These defaults are also documented in `rules.md`.

## Development

For day-to-day development in a clone of the repository:

```powershell
pdm install --dev
```

Common checks:

```powershell
pdm run lint
pdm run typecheck
pdm test
```

For CI or reproducible installs from the lockfile, use:

```powershell
pdm sync --clean --dev
```

## Webots backend metadata

The `webots` backend emits a single Python controller file:
- file extension: `.py`
- embeds the generated Python TENNCell model without the standalone CSV CLI
- creates a Webots `Robot`
- binds TENNCell input variables to configured Webots device read methods
- binds TENNCell output variables and initialization values to configured device write methods
- uses `webots.timestep` when provided, otherwise reads the basic timestep from the robot
- can optionally write a CSV trace during controller execution with `webots.csv`

Each declared TENNCell input must have a binding with `read_method`.
Each declared TENNCell output must have a binding with `write_method`.
The rules use TENNCell variable names; the bindings control which Webots methods read or write those variables.

Initialization entries under `webots.init` must refer to bindings with `write_method`.
CSV entries under `webots.csv.variables` may refer to any TENNCell variable, not only inputs or outputs.
By default, Webots CSV rows are written after controller steps and `_step` starts at `1`; set `include_initial: true` to add an initial `_step: 0` row. `webots.csv.delimiter` defaults to comma, and `webots.csv.precision` can be set to a non-negative integer to format numeric CSV values with fixed decimal places.

The backend does not generate Webots world or PROTO files. It only emits the
controller glue that reads Webots devices, advances the generated TENNCell model,
and writes outputs back to Webots devices.

```yaml
...
speed -> right_speed
...

webots:
  controller_name: e_puck_pid_controller
  timestep: 64
  bindings:
    left_sensor:
      device: ps0
      read_method: getValue
    right_sensor:
      device: ps7
      read_method: getValue
    left_speed:
      device: left wheel motor
      write_method: setVelocity
    right_speed:
      device: right wheel motor
      write_method: setVelocity
    left_position:
      device: left wheel motor
      write_method: setPosition
    right_position:
      device: right wheel motor
      write_method: setPosition
  init:
    left_position: inf
    right_position: inf
  csv:
    file: e_puck_pid.csv
    variables: [left_sensor, right_sensor, left_speed, right_speed]
    include_step: true
    include_time: true
    include_initial: true
    delimiter: ";"
    precision: 3
```

## Verilog backend metadata

The Verilog backend metadata allows you to describe port and internal variable shapes. It also allows you to include external RTL modules.

Supported expression subset:
- constants
- local variables
- qualified references
- addition and subtraction
- unary minus
- constant multiplication and constant division
- boolean comparisons
- boolean `&&`, `||`, `!`

Rejected constructs:
- generic function calls
- variable-by-variable multiplication
- non-constant division
- arrays

Each TENNCell module uses its own `real_encoding`. Boundary conversions are inserted automatically for imported TENNCell IO and external ports.
In the Verilog backend, it is recommended to use `zero_reset_mode: true`. This simplifies the generated code by removing the checks for variable consumption.

Here is a simple led blink example:
```yaml
module:
  name: fpga_blink
  zero_reset_mode: true
verilog:  
  real_encoding:
    kind: fixed_point
    signed: false
    width: 48
    frac_bits: 10
  clock: clk
  reset: rst
  ports:
    - name: led
      direction: output
      kind: logic
      width: 1
      signed: false

constants:
  BLINK_DELAY: 27000000 

cells:
  - id: 1
    contents:
      - counter = 0
      - led = 0
    output: [led]

rules:
  - if: counter < BLINK_DELAY
    then: 
      # Increment the counter
      - counter + 1 -> counter
      # Keep the led state (otherwise it resets to zero)
      - led -> led
    else: 
      # When the delay expires, toggle the LED.
      # The counter resets to zero by itself (because of the zero_reset_mode)
      - led == 0 | 1 -> led
      - led > 0 | 0 -> led
```
The next example shows the use of an external module. It reads `rx_valid` and `rx_data` from the UART external and turns the LED on or
off when the received byte is `1` or `0`.


```yaml
module:
  name: fpga_uart_led
  zero_reset_mode: true

verilog:
  real_encoding:
    kind: fixed_point
    signed: true
    width: 32
    frac_bits: 16
  clock: clk
  reset: rst
  ports:
    uart_rx:
      direction: input
      width: 1
    led:
      direction: output
      width: 1
  externals:
    uart0:
      header: uart.header.yaml
      parameters:
        CLOCK_FREQ: 50000000
        BAUD_RATE: 115200
      connections:
        clk: clk
        rst: rst
        rx: uart_rx

cells:
  - id: 1
    contents:
      - uart_rx = 0
      - led = 0
      - rx_data = 0
      - rx_valid = 0
    input: [uart_rx]
    output: [led]

rules:
  - rx_valid == 1 && rx_data == 1 | 1 -> led
  - rx_valid == 1 && rx_data == 0 | 0 -> led
```


More details can be seen in the examples under `examples/fpga/`, especially `blink_uart/`, `blink_uart_typed/`, `fpga_uart_led/`, `sensor_controller/`, `fpga_spi_gpio_bridge/`, and `axii/`.

### Technical RTL generation details

The `verilog` backend emits SystemVerilog-style RTL:
- file extension: `.sv`
- wraps each generated module with `` `default_nettype none`` and keeps it in effect throughout the generated file
- module parameters in the module header
- `always_comb` for next-state logic
- `always_ff` for sequential updates
- fixed-point values stay as integer literals in the emitted RTL, wrapped in generated module-local `localparam` aliases such as `_VAL_1_0`
- generated fixed-point state, helper signatures, and literals follow `verilog.real_encoding` 
- boundary conversions use generated helper functions
- if a TENNCell input/output is described in `verilog.ports`, the generated RTL converts between the module-local fixed-point encoding and the declared Verilog port format at the module boundary
- if a TENNCell module does not declare `verilog.ports`, the Verilog backend infers the full module boundary from that module's input/output variables and `verilog.real_encoding`
- if a TENNCell input/output is described in `verilog.externals`, the generated RTL rewires that variable internally to the external module rather than exposing it at the top-level interface; if the target is a TENNCell output that is also a top-level port, the top-level port is driven directly from the external module output
- plain variable names such as `sample` or `alarm` refer to the local TENNCell variable, while Verilog port names are emitted only through `verilog.ports`
- fixed-point to integer top-port conversion truncates toward zero
- generated literal aliases are documented with comments showing the original source values and fixed-point format


## Backend Boundaries

- Python simulation and `nnc-gen -t python` use TENNCell model semantics and support TENNCell imports only.
- Python simulation and the Python backend do not consume `verilog.externals`.
- Verilog generation uses the TENNCell model plus `verilog.real_encoding`, `verilog.ports`, `verilog.externals`, and TENNCell imports.
- Webots generation uses the TENNCell model plus `webots.bindings` / `webots.init`.
- Webots generation emits controller code only: one Python controller for the root YAML file, with no world, PROTO, or external RTL files.

## Examples

See `examples/` for:
- standalone YAML under `examples/simple/`, such as `example1.yaml`, `example2.yaml`, `example3.yaml`, `example3io.yaml`, `example3o.yaml`, `example_add.yaml`, `ballistic.yaml`, and `ballistic_if.yaml`
- recursive conditional YAML in `examples/fsm/if_recursive.yaml`
- FSM-oriented YAML in `examples/fsm/fsm_counter.yaml` and `examples/fsm/fsm_dual.yaml`
- import-only Python composition in `examples/composition/python_composed/`
- imported multicell Python composition in `examples/composition/imported_composition/`
- Verilog composition examples in `examples/composition/verilog_composed/`
- FPGA-oriented examples under `examples/fpga/`, including standalone `blink.yaml`, `blink_if.yaml`, and `ledwalk.yaml`, plus dedicated folders for `blink_uart/`, `blink_uart_typed/`, `sensor_controller/`, `fpga_uart_led/`, `fpga_spi_gpio_bridge/`, and `axii/`
- Webots controller examples under `examples/webots/`, including `e_puck_pid/` and `pioneer3_dx_obstacle_avoidance/`

## Notes
- Top-level `name` and `description` are treated as metadata and ignored by Verilog generation.
- Detailed behavior and schema rules live in `rules.md`.


Since version `0.3.0`, AI has been used to help with code-generation and refactoring work in this repository.

The project is distributed under the MIT license.
