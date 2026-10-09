# Unit Test Contracts

This file records the current unit-test contract surface for TENNCell. The tests
should verify these promises, not internal implementation details.

## Test Inputs

- Complete models, scenario traces, and golden outputs are checked-in fixtures under `tests/fixtures/`, each with a short YAML comment naming the scenario it serves.
- Inline YAML or CSV is used only for validation and error tables: a few lines per case, next to the expected message (often with its line number).
- Truth-table tests of the native checker and the MC2 translation build properties and traces in Python, on the shared fixture `tests/fixtures/verification/pt_model.yaml`.

## Contract Map

- `tests/unit_tests/model/` covers the core runtime model.
- `tests/unit_tests/parser/` covers parser and value semantics.
- `tests/unit_tests/yaml/` covers YAML loading, value resolution, includes, and lowering.
- `tests/unit_tests/transformers/base/` covers the transformer base class.
- `tests/unit_tests/transformers/package/` covers package exports.
- `tests/unit_tests/transformers/python/` covers Python backend behavior.
- `tests/unit_tests/transformers/verilog/` covers Verilog backend behavior.
- `tests/unit_tests/transformers/webots/` covers Webots backend behavior.
- `tests/unit_tests/transformers/mc2/` covers MC2 query generation from raw entries and generic properties.
- `tests/unit_tests/verification/test_mc2_translation.py` covers the MC2 translation of every generic property kind (strict and weak, `from_step`, bounds) and of conditions.
- `tests/unit_tests/verification/` covers verification section parsing, placeholders, and reference binding.
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

- `load_yaml_data_and_locations()` resolves plain YAML values with YAML 1.2 core rules (including `0o...` octal) plus `0b...` and `1_000` numbers: `on`/`off`/`yes`/`no` are strings, a leading zero is decimal, an exponent makes a float, and dates and `1:30` stay strings, for both values and keys.
- `module.zero_reset_mode` and the Verilog `signed` fields accept only YAML booleans and report other values with their YAML line.
- `parse_expression()` parses valid TENNCell expressions into the expected AST shape.
- `parse_condition()` parses boolean conditions and rejects invalid syntax with a clear error.
- `parse_variable_assignment()` parses assignments into variable mappings and respects the provided context.
- Qualified references such as imported names are parsed as references, not rewritten by the parser.
- `ArrayValue` behaves like a typed, indexable sequence with predictable `str()`, `repr()`, equality, containment, iteration, and length behavior.
- `FloatValue` and related numeric value objects preserve arithmetic and comparison semantics.
- `BooleanExpression` and `Expression` subclasses evaluate correctly, expose referenced variables, and render stable string representations.

## Transformer Contracts

- `BaseTransformer` provides the shared output buffer workflow used by backends.
- `nnc.transformers` exports `BaseTransformer`, `Mc2Transformer`, `PythonTransformer`, `VerilogTransformer`, and `WebotsTransformer`.
- `BaseTransformer.transform_files()` defaults to one file built from `transform()` and `get_file_extension()`.
- `PythonTransformer` emits the standalone Python backend for a single TENNCell system.
- For the same inputs and deterministic expressions supported by the generated Python backend, generated Python `step()` is bitwise-identical to `NncSystem.step()`, including the evaluation order of guards and productions, over many steps and in closed feedback loops.
- Every default `MathFunctions` function has a generated-Python mapping, and each one gives the same result as the simulator; `random()` is executable but not compared with the simulator.
- Functions without a generated-Python mapping, and runtime overrides of default functions, are rejected at generation time; `nnc-gen -t python` reports the error and continues with the remaining files.
- Python generation rejects documents with no model variables or semantic imports instead of emitting an invalid empty class.
- Qualified FSM state references resolve to their state constants in standalone and composed generated Python.
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
- `Mc2Transformer` emits `.mc2.pltl`, `.mc2.ids`, and `.mc2.columns` from `mc2.raw` followed by the generic properties for MC2, requires at least one emitted entry, rejects empty or multi-line queries, function calls in properties targeting `mc2`, and property IDs equal to emitted raw IDs, and warns about skipped generic properties, weak-semantics approximations, and about columns that are not root outputs; with a `webots.csv` section, only about columns that are neither root outputs nor in `webots.csv.variables`, and about a Webots log without `include_step` or with a delimiter MC2 cannot read.

## Verification Contracts

- `parse_verification_section()` returns `None` when the section is absent and a `VerificationConfig` otherwise.
- Unknown keys, invalid `trace_semantics`, malformed `environment` entries, and reserved or unknown backend names are rejected with YAML file and line.
- `native.raw` and `sva.raw` are rejected; `mc2.raw` entries require an identifier `id` and string `code`, and lose exactly one final newline.
- Raw IDs are unique within `mc2.raw`; property IDs are unique among `properties`.
- Generic properties are parsed into `GenericProperty` with their kind, condition, trigger, bounds, `from_step`, and `targets`; every invalid key combination and bound is rejected with its YAML line.
- `bind_property()` parses property conditions against the model, rejects unknown names, `random()`, and runtime-registered or overridden functions, and records the trace columns and functions each property uses.
- `check_properties()` implements the native truth table for every kind under strict and weak semantics (row positions, `from_step`, empty ranges, overlapping triggers, persistence end cases, reported rows and labels), reports non-native targets as `skipped`, and raises `VerificationError` for missing or non-finite used columns and for condition evaluation errors.
- `Trace` rejects empty traces, length mismatches, non-finite or non-increasing labels, and rows with different columns.
- `evaluate_expression()`/`evaluate_boolean()` give identical results for bound variables and row values, call functions left to right, and short-circuit `&&`/`||`.
- Include merging concatenates `verification.properties` and `verification.backends.mc2.raw`, keeping source locations.
- `parse_template()` splits raw code into text and `${name}` placeholders, handles `$${` escapes, and rejects unclosed, empty, or invalid placeholders.
- `resolve_reference()` resolves variables, constants, FSM states, imported inputs/outputs, and aliases (to their target), and rejects unknown and ambiguous names.
- `bind_verification()` rejects environment keys that are not root inputs and reports placeholder errors at the raw entry's YAML line.

## CLI Contracts

- `nnc-gen` processes requested files in batch mode.
- CLI failures do not abort the remaining inputs.
- Exit status is `0` on full success and `1` when any file fails.
- Invalid transformer types and missing files produce clear error messages.
- `nnc-gen -t mc2` writes the three MC2 files with `--output-suffix`, prints transformer warnings to stderr, and continues the batch after an invalid file.
- `nnc-verify` simulates (`--steps`: N+1 rows for autonomous models; `--inputs`: N records give N+1 rows) or reads a recorded `--trace` (step-column labels, `--first-step`, `--no-step-column`, `--skip-lines`, whitespace delimiter, unused and empty-named columns ignored, a PeP-style log fixture), reports every property status in a table or JSON, and exits `0` without failures, `1` on a failure or operational error, `2` on usage errors.
- `nnc-sim --csv-include-step` prepends a `step` column to IO-mode CSV (initial row `0`, after-step rows from `1`); without it IO mode keeps output-only columns.

## Notes

- These contracts are still being refined.
- Test fixtures live under `tests/fixtures/` for functional scenarios.
- `examples/` should not be the source of truth for tests.
