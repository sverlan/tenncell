CLI
===

This section documents the two command-line interfaces:

- `nnc-sim` for simulation
- `nnc-gen` for Python, Verilog, and Webots code generation

Simulation CLI
--------------

The simulation command executes a TENNCell system directly from YAML.

.. code-block:: console

   nnc-sim SYSTEM.yaml [INPUT.csv] [OUTPUT.csv] [options]

Key behavior:

- `nnc-sim` reads a single YAML system.
- The simulator accepts standalone TENNCell systems and composed imports.
- The simulator uses TENNCell model semantics and does not consume `verilog.externals`.
- IO mode is the default. It always reads CSV input rows and emits CSV output rows.
- In compute mode, no CSV input is consumed. The system runs for a fixed number of steps and prints the output state.
- `--csv` applies only to compute mode and switches that output to CSV.
- The command returns exit code `0` on success and `1` for runtime or loader errors.

Useful options:

- `-c` / `--compute_mode`
- `-s` / `--steps`
- `--csv`

.. autofunction:: nnc.cli.main

Transformer CLI
---------------

The transformer command generates code from TENNCell YAML for the selected backend.

.. code-block:: console

   nnc-gen -t python SYSTEM.yaml
   nnc-gen -t verilog SYSTEM.yaml
   nnc-gen -t webots SYSTEM.yaml

Common behavior:

- `--import-path` and `--import-paths` extend the lookup paths for imported TENNCell files and external headers.
- `--output-dir` controls where generated files are written.
- `--output-suffix` appends a suffix to generated filenames.
- `--verbose` prints progress and errors.
- YAML loader and transformer errors include the originating YAML file path and line number when available, including imported-file failures.

Python backend:

- Emits a single composed Python file for the root system.
- Supports TENNCell imports only; it does not consume `verilog.externals`.
- The generated script keeps the CSV command-line behavior documented in the runtime tests.

Verilog backend:

- Emits one SystemVerilog file per module in the import closure.
- Requires a `verilog:` section with `real_encoding` and optional `ports` / `externals`.
- Supports TENNCell imports and `verilog.externals`.
- If a TENNCell module does not declare `verilog.ports`, the Verilog backend infers the full module boundary from that module's input/output variables and `verilog.real_encoding`.
- `verilog.ports` describes the generated module interface for TENNCell input/output variables.
- `verilog.ports` entries may specify `kind`; it defaults to `logic` when omitted.
- `verilog.externals` describes internal rewiring to external modules, either via `header` or inline `schema`.
- `clock` and `reset` are special generated boundary signals and default to `clk` / `rst`.

Example:

.. code-block:: yaml

   verilog:
     clock: clk
     reset: rst
     real_encoding:
       kind: fixed_point
       width: 32
       frac_bits: 16
       signed: true
     ports:
       uart_rx:
         direction: input
         width: 1
       uart_tx:
         direction: output
         width: 1
     externals:
       uart0:
         header: uart.header.yaml
         parameters:
           FIFO_DEPTH: 16
         connections:
           rx: uart_rx
           tx: uart_tx

Webots backend:

- Emits a single Python controller file.
- Requires a `webots:` section with controller settings, per-variable device bindings, and optional one-time init values.
- Uses the resolved TENNCell model only; no Webots world, PROTO, or header files are generated.
- Each TENNCell input must have a binding with `read_method`.
- Each TENNCell output must have a binding with `write_method`.
- Each `webots.init` entry must target a binding with `write_method`.
- The backend does not consume `verilog` configuration.

Example:

.. code-block:: yaml

   webots:
     controller_name: e_puck_pid_controller
     timestep: 64
     bindings:
       left_sensor:
         device: ps0
         read_method: getValue
       left_speed:
         device: left wheel motor
         write_method: setVelocity
       left_position:
         device: left wheel motor
         write_method: setPosition
     init:
       left_position: inf

Backend boundaries:

- Python simulation and Python generation support TENNCell imports only and do not use `verilog.externals`.
- Verilog generation supports TENNCell imports, `verilog.ports`, and `verilog.externals`.
- Webots generation emits controller code only: it wraps generated Python TENNCell code with Webots device IO and does not generate worlds, PROTO files, or RTL.

.. autofunction:: nnc.cli_transform.main
.. autofunction:: nnc.cli_transform.get_transformer
