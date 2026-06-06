# Functional Contracts

This file lists end-to-end behaviors that should be covered by YAML fixtures and
functional tests.

## System loading and stepping

- A minimal YAML system loads successfully and can execute `step()`.
- `zero_reset_mode` resets non-input state as documented.
- Imports are resolved through the YAML loader and participate in stepping.
- Constants and aliases affect the resulting runtime behavior.

## Python generation

- Standalone Python generation emits a runnable script for the root system.
- Composed Python generation emits reusable module classes for imported systems.
- CSV input and output handling behave consistently for generated Python.
- Empty input produces the documented warning or empty-result behavior.

## Verilog generation

- Verilog generation emits the expected module structure for the root system.
- `verilog.real_encoding` is required and affects generated numeric behavior.
- Clock and reset wiring are emitted from the Verilog section.
- Top ports are emitted with the expected direction and width.
- External module headers and instances are parsed and wired correctly.
- Imported modules contribute their own Verilog hardware configuration.

## CLI

- The transform CLI produces the expected output files for supported targets.
- CLI failures return a non-zero exit status and a useful error message.
- Batch transform behavior remains stable for the supported examples.

## Contract rule

- Each functional contract should be backed by one or more stable YAML fixtures.
- Functional tests should verify observable output, not internal helper calls.
