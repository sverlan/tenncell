# Unit Test Contracts

This file records the current unit-test contract surface for TENNCell. The tests
should verify these promises, not internal implementation details.

## Contract Map

- `tests/unit_tests/model/` covers the core runtime model.
- `tests/unit_tests/parser/` covers parser and value semantics.
- `tests/unit_tests/transformers/base/` covers the transformer base class.
- `tests/unit_tests/transformers/package/` covers package exports.
- `tests/unit_tests/transformers/python/` covers Python backend behavior.
- `tests/unit_tests/transformers/verilog/` covers Verilog backend behavior.
- `tests/unit_tests/transformers/webots/` covers Webots backend behavior.
- `tests/cli_tests/` covers CLI behavior and command-line contract.

## Core Model Contracts

- `NncSystem.from_yaml()` loads a TENNCell YAML file into the in-memory model.
- A missing `module.name` defaults to the source filename stem.
- `zero_reset_mode` defaults to `false` when absent.
- Imported modules are resolved recursively and their import graph is acyclic.
- `NncSystem.step()` applies active rules, updates state, and returns declared outputs.
- `NncSystem.validate_references()` rejects invalid local, imported, and qualified references.
- Constant expressions are evaluated in declaration order and may only reference earlier constants.
- FSM sugar is lowered into state constants, initialization, and guarded rules.

## Parser and Value Contracts

- `parse_expression()` parses valid TENNCell expressions into the expected AST shape.
- `parse_condition()` parses boolean conditions and rejects invalid syntax with a clear error.
- `parse_variable_assignment()` parses assignments into variable mappings and respects the provided context.
- Qualified references such as imported names are parsed as references, not rewritten by the parser.
- `ArrayValue` behaves like a typed, indexable sequence with predictable `str()`, `repr()`, equality, containment, iteration, and length behavior.
- `FloatValue` and related numeric value objects preserve arithmetic and comparison semantics.
- `BooleanExpression` and `Expression` subclasses evaluate correctly, expose referenced variables, and render stable string representations.

## Transformer Contracts

- `BaseTransformer` provides the shared output buffer workflow used by backends.
- `nnc.transformers` exports `BaseTransformer`, `PythonTransformer`, `VerilogTransformer`, and `WebotsTransformer`.
- `PythonTransformer` emits the standalone Python backend for a single TENNCell system.
- Composed Python generation emits one file for the import closure and preserves module class structure.
- Generated Python code keeps the current CSV command-line behavior.
- `zero_reset_mode` changes the generated step/reset behavior as documented.
- External modules are rejected by the Python backend.
- `VerilogTransformer` emits SystemVerilog-style RTL for the import closure.
- Verilog generation requires explicit backend configuration for numeric encoding and boundary metadata.
- Generated Verilog includes `default_nettype` guards, module parameters, state declarations, and sequential/next-state logic.
- Port boundary conversions are inserted automatically when local TENNCell values cross `verilog.ports` or external module boundaries.
- `verilog.ports` preserves optional `kind` metadata and defaults it to `logic` when omitted.
- Unsupported Verilog expressions are rejected with clear errors.
- FSM sugar is lowered into generated Verilog state logic and constants.
- `WebotsTransformer` emits a standalone Python controller for Webots.
- Webots generation requires a `webots` YAML section with bindings for declared TENNCell inputs and outputs.

## CLI Contracts

- `nnc-gen` processes requested files in batch mode.
- CLI failures do not abort the remaining inputs.
- Exit status is `0` on full success and `1` when any file fails.
- Invalid transformer types and missing files produce clear error messages.

## Notes

- These contracts are still being refined.
- Test fixtures live under `tests/fixtures/` for functional scenarios.
- `examples/` should not be the source of truth for tests.
