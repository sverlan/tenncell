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
- A model name emitted as a SystemVerilog keyword is rejected by `transform` and `observe` with an error naming it and its role: the module name, a port (inferred, renamed, clock), a constant, an import or external alias, an imported module's name or port, and a variable emitted as a wire (bound to an imported or external output).
- `VerilogTransformer.observe` reports exactly every root variable and imported input/output, and every connectable signal with the width and signedness of its declaration in the RTL that `transform` emits, for every model with a Verilog golden file (root and imported modules); renamed ports, imported outputs/inputs, binding wires and converted (non-connectable) connections are covered; observing never changes the emitted RTL; the observation is read-only.
- The SVA checker shell exposes exactly the selected plain RTL signals, copies root and imported inputs so a sampled row carries the value that produced it (with distinct row-0 initial values even when they share an RTL signal), keeps its 64-bit reporting row counter out of formal builds, renders raw placeholders through checker-visible signals and encoded constants, and emits a bind file only when formal output is requested.
- SVA monitors for every property kind (with `from_step`) match a golden checker; their conditions read imported outputs, FSM states and constants as the RTL encodes them; weak semantics report open obligations as `pending` with `SVA_OPEN ... end`; no step counter is emitted when no property needs one; zero bounds (`after: 0`, `within: [0, 0]`, `then_always` without `after`) have no history vector or counter, and no empty or reversed declaration is emitted; a checker port named like the report task, a literal parameter (including one a conversion helper creates) or a conversion helper is rejected. Generation warns, with the exact count, when the monitor state exceeds 65,536 bits (pending bits, age counters, flags and the shared step counter are all counted; checked at 65,536 and 65,537 bits).
- Two imports of the same file are separate system instances with their own state.
- Import connections accept YAML numbers (stored as decimal text, given as values, encoded for the child's port in Verilog and emitted as literals in Python); booleans, lists, non-finite or too large numbers and unknown plain names are rejected when the model is loaded. Numbers driving external input ports are encoded per port (fixed point, one bit, logic), `null` and `0` drive 0, and a number on an external output port is rejected with its line.
- A step gives every import values of the configuration before the step (numerical P system semantics): an import reading another import's output sees it one step later, imports may read each other in a cycle, and the generated Python step behaves the same.
- `NncSystem.last_import_inputs` holds the inputs given to each direct import in the last step (also when the child consumed them), as a copy.
- FSM sugar is lowered into generated Verilog state logic and constants.
- `WebotsTransformer` emits a standalone Python controller for Webots.
- Webots generation requires a `webots` YAML section with bindings for declared TENNCell inputs and outputs.
- `Mc2Transformer` emits `.mc2.pltl`, `.mc2.ids`, and `.mc2.columns` from `mc2.raw` followed by the generic properties for MC2, requires at least one emitted entry, rejects empty or multi-line queries, function calls in properties targeting `mc2`, and property IDs equal to emitted raw IDs, and warns about skipped generic properties, weak-semantics approximations, and about columns that are not root outputs; with a `webots.csv` section, only about columns that are neither root outputs nor in `webots.csv.variables`, and about a Webots log without `include_step` or with a delimiter MC2 cannot read.

## Verification Contracts

- `parse_verification_section()` returns `None` when the section is absent and a `VerificationConfig` otherwise.
- Unknown keys, invalid `trace_semantics`, malformed `environment` entries, and reserved or unknown backend names are rejected with YAML file and line.
- `native.raw` is rejected; `mc2.raw` and `sva.raw` entries require an identifier `id` and string `code`, and lose exactly one final newline (an MC2 entry must then be one line; an SVA entry may span several).
- Raw IDs are unique within `mc2.raw`; property IDs are unique among `properties`.
- Generic properties are parsed into `GenericProperty` with their kind, condition, trigger, bounds, `from_step`, and `targets`; every invalid key combination and bound is rejected with its YAML line.
- `bind_property()` parses property conditions against the model, rejects unknown names, `random()`, and runtime-registered or overridden functions, and records the trace columns and functions each property uses.
- `check_properties()` implements the native truth table for every kind under strict and weak semantics (row positions, `from_step`, empty ranges, overlapping triggers, persistence end cases, reported rows and labels), reports non-native targets as `skipped`, and raises `VerificationError` for missing or non-finite used columns and for condition evaluation errors.
- `Trace` rejects empty traces, length mismatches, non-finite or non-increasing labels, and rows with different columns.
- `evaluate_expression()`/`evaluate_boolean()` give identical results for bound variables and row values, call functions left to right, and short-circuit `&&`/`||`.
- Include merging concatenates `verification.properties`, `verification.backends.mc2.raw` and `verification.backends.sva.raw`, keeping source locations.
- `backends.sva.mode` is rejected with a pointer to the generation option; `backends.sva.raw` entries (multi-line code) are parsed.
- `SvaOptions` rejects invalid combinations; SVA selection emits, skips with a reason, or rejects each generic property (functions, RTL-inexpressible conditions, non-signal values, bound limit, unbounded eventually per mode), rejects ID collisions with raw entries and concurrent style with weak semantics, binds raw placeholders to plain RTL signals, and errors when nothing is emitted; external sources are checked before writing and copied without cleaning the directory.
- `SvaTransformer` writes the RTL closure exactly as `VerilogTransformer` emits it, rejects two modules with the same RTL file name, and warns about externals without sources.
- The concurrent-style checker matches a golden file with every property kind (one assertion or cover each, strong operators, `nexttime[n] always` for `then_always`), has no report task, and its testbench ends with `$finish` without calling `sva_report`.
- SVA formal output: environment ranges are encoded inward for the port (fixed point and logic), clipped to the port with a warning, and rejected when no port value remains or the range is not finite; the formal checker (reset scheme, assumptions on live ports, one labelled assert or cover per property) and the `.sby` file (tasks `bmc`, `cover`, `prove_kind`, `prove_pdr`) match goldens; the step counter and `then_always` age counters get invariant assertions; unbounded `eventually` gets a liveness check instead of an assertion (see SVA liveness); copied sources are read by name and a source named like a generated file, and file names with whitespace in formal mode, are rejected; duplicate source names are detected ignoring case.
- SVA liveness: in modes `formal` and `both` an unbounded `eventually` is selected without warning (also when it lists `sva`) and gets no assertion; all of them feed one `<module>_sva_live` instance `sva_liveness` with the conjunction of their `seen || hit_now` signals and enabled while the reset is inactive (either polarity) (the `seen` flag is monitor state, the hit gated by `from_step`); the helper file `<stem>_sva_live.v` holds the `$live` cell; the `.sby` gets the `live` task (mode live, `aiger suprove`, `~live: depth`, `read_verilog -formal -icells` of the helper, `live: chformal -assert -remove`, the helper in `[files]`); without such a property, or in simulation mode, there is no helper and no task, and a stale helper file is obsolete; a helper module name that is an RTL module is rejected.
- SVA witness replay: a Yosys witness gives the rows (`steps - 3`) and the input port values of steps `1..rows` (two's complement for signed ports); the replay writes the hex, decoded inputs and testbench with a comment naming the witness and row, or only the number of rows for a model without inputs; ports split into fragments are assembled by offset (with `init_only` fragments only in step 0); unknown input bits are replayed as 0; both reset polarities are handled; non-witness files, malformed signals, wrong bit counts or characters, too short witnesses, unknown reset bits, reset not active only at step 0, and missing ports are rejected; `--sva-replay` is one of the three exclusive stimulus options; the replay testbench calls `sva_replay_check` on the witness row and succeeds only if the failure or cover is reproduced, the note names the expected row and says the witness is matched by ports only, and replay with the concurrent style or without generic properties is rejected.
- SVA stimulus: each input record is encoded for its RTL port (signed and unsigned fixed point with the port width, logic of any width, one bit), written to `<stem>_inputs.hex` as masked, zero-padded hex words (one line per record, inputs in declaration order) and decoded back to `<stem>_inputs_decoded.csv`; non-finite values and values (or initial values) that do not fit the port, including finite values whose scaling overflows, are rejected with file, line and input; checker and testbench module names that are RTL module names are rejected; values outside an `environment` range give one warning per input; a header without records gives a testbench without stimulus array, `$readmemh` or loop, and no hex file; `--sva-steps` gives a testbench without stimulus files; a checker without generic properties gets a testbench that does not call `sva_report`; the stimulus source must fit the model (inputs vs steps, one of them in simulation).
- `parse_template()` splits raw code into text and `${name}` placeholders, handles `$${` escapes, and rejects unclosed, empty, or invalid placeholders.
- `resolve_reference()` resolves variables, constants, FSM states, imported inputs/outputs, and aliases (to their target), and rejects unknown and ambiguous names.
- `bind_verification()` rejects environment keys that are not root inputs and reports placeholder errors at the raw entry's YAML line.

## CLI Contracts

- `nnc-gen` processes requested files in batch mode.
- CLI failures do not abort the remaining inputs.
- Exit status is `0` on full success and `1` when any file fails.
- Invalid transformer types and missing files produce clear error messages.
- `nnc-gen -t mc2` writes the three MC2 files with `--output-suffix`, prints transformer warnings to stderr, and continues the batch after an invalid file.
- `nnc-gen -t sva --sva-style concurrent` writes `assert property` checks; with weak semantics it is an error (exit `1`).
- `nnc-gen -t sva` writes the RTL closure, checker, testbench and (with `--sva-inputs`) the hex and decoded input files; `--delimiter`/`--skip-lines` reach the input reader; `--sva-source` files are copied to `sva_sources/` (no directory without sources). Formal mode writes `<stem>.sby`, the checker and the bind file, without testbench (depth `D + 2` in the `.sby`); `both` writes everything; a stimulus in formal mode is an error (exit `1`). Option misuse is a usage error (exit `2`): `--sva-*`, `--delimiter` or `--skip-lines` with another target, concurrent style with formal modes, `--sva-depth` in simulation mode, invalid bounds or steps, `--sva-inputs` with `--sva-steps`, `--delimiter`/`--skip-lines` without `--sva-inputs`, `--output-suffix`. A stimulus that does not fit the model is an error (exit `1`) and writes nothing.
- `nnc-verify` simulates (`--steps`: N+1 rows for autonomous models; `--inputs`: N records give N+1 rows, and the input columns of row k hold record k even when a rule consumed the input; imported input columns hold the value given to the child, even when the child consumed it) or reads a recorded `--trace` (step-column labels, `--first-step`, `--no-step-column`, `--skip-lines`, whitespace delimiter, unused and empty-named columns ignored, a PeP-style log fixture), reports every property status in a table or JSON, and exits `0` without failures, `1` on a failure or operational error, `2` on usage errors.
- `nnc-sim --csv-include-step` prepends a `step` column to IO-mode CSV (initial row `0`, after-step rows from `1`); without it IO mode keeps output-only columns.

## Notes

- These contracts are still being refined.
- Test fixtures live under `tests/fixtures/` for functional scenarios.
- `examples/` should not be the source of truth for tests.
