# Changelog

## 0.9.0

- New user guide `docs/generic_properties.md`: syntax and semantics of every generic property kind, the row-based time model, `strict`/`weak` end of trace, reporting, targets and the MC2 translation, with worked examples.
- `examples/verification/fsm_counter_mc2.yaml` now has generic properties of several kinds and documents the full workflow: `nnc-verify` on a simulated run, and a recorded `nnc-sim` trace checked by both `nnc-verify` and MC2.
- `nnc-gen -t mc2` now translates generic verification properties into MC2 queries, appended after the raw entries. Properties that call functions are skipped with a warning (an error if they target `mc2` explicitly); an emitted property ID that equals a raw MC2 ID is an error; with `trace_semantics: weak`, warnings explain how MC2 approximates `pending`. The error for a model with nothing to emit is now "No MC2 verification entries found".
- Internal: generic property modules moved to `nnc.verification.generic_properties` (`binding`, `native`, `conditions`, `mc2`).
- Added `nnc-verify`, which checks generic verification properties with the built-in `native` checker on a simulated run (`--steps`, `--inputs`) or a recorded trace (`--trace`), with table or JSON output and exit status `1` when a property fails.
- Generic verification properties (`verification.properties`) are now fully parsed and bound to the model: every property kind, bounds, `from_step`, and conditions checked against the model's names and functions. API change: `nnc.verification.PropertyStub` is replaced by `GenericProperty`.
- `nnc-gen -t mc2` now takes the Webots controller's CSV log (`webots.csv`) into account: columns listed in `webots.csv.variables` no longer trigger the "not root outputs" warning, and it warns when the log has no step column or a delimiter MC2 cannot read.
- Documented MC2 v2.0beta2 query pitfalls in `docs/verification.md`: `->` combined with `X` always evaluates to false, the strict end of trace and its weak form, nested `X` for bounded windows, and `G` versus `F` for "always" rules.

## 0.8.1

- Changed YAML value resolution to YAML 1.2 core rules (including `0x` and `0o` numbers, and keeping `0b` and `1_000`). Behavior change: plain `on`, `off`, `yes`, `no` are now strings instead of booleans, `010` is 10 instead of octal 8, `1e5` is a float, and dates and `1:30` stay strings. No file in the repository is affected.
- Fixed `module.zero_reset_mode` and the Verilog `signed` fields accepting non-boolean values: `zero_reset_mode: "false"` silently enabled zero-reset mode. These settings now accept only `true` or `false`.

- Fixed generated Python and Webots `step()` arithmetic: consumed variables now start from zero before productions are added, so deterministic expressions supported by generated Python produce results bitwise-identical to the simulator. Previously `((x + c1) + c2) - x` produced rounding differences that could change closed-loop behavior, and `nan` when the old value was infinite.
- Fixed generated Python and Webots code crashing with `NameError` on valid models:
  - all default functions are now supported (`acos`, `asin`, `atan`, `atan2`, `cosh`, `sinh`, `tanh`, `degrees`, `radians`, `log10`, and `hypot` were missing, and `random()` lost its parentheses);
  - qualified FSM states such as `ctrl.ACTIVE` used in another FSM's rules now resolve to their state constant.
- Generated Python now rejects runtime-registered custom functions, including overrides of default names, at generation time with a clear error instead of silently changing behavior or producing code that fails when run.
- Generated Python now rejects external headers and include-only documents with a clear "nothing to generate" error instead of emitting an invalid empty class.

## 0.8.0

- Added the planned `verification` section parser and MC2 raw query generation through `nnc-gen -t mc2`.
- Added MC2 query, ID, and trace-column file emission with placeholder validation against TENNCell model references.
- Added IO-mode `nnc-sim --csv-include-step` support and documented the MC2 v2.0beta2 trace/query workflow.

## 0.7.3
- Added CSV control options like `--csv-delimiter`
- Added an include mechanism to include YAML fragments.
- Added the syntactic sugar allowing to index variables and rules (via repeat node).

## 0.7.2

- Added optional Webots controller CSV logging through `webots.csv`, including selected variable columns and optional step/time columns.

## 0.7.1

- Rejected duplicate YAML initial declarations in `cells[].contents`, including same-cell redeclarations and cross-cell redeclarations.
- Documented YAML test fixture preferences for future agent work.

## 0.7.0

- First public release

## 0.6.11

- Flattened the Verilog backend by moving the emitter mixins into `src/nnc/transformers/verilog/generation/` and removing the compatibility shim modules.
- Reduced the public Verilog package exports to the contract dataclasses and encoding types.

## 0.6.10

- Lowered Verilog constants in the expression domain as an optimization so typed comparisons and arithmetic can keep live boundary signals in their native encoding.
- Updated Verilog snapshots and expression-emitter coverage to reflect the new constant-lowering behavior.

## 0.6.9

- Refined the Verilog boundary contract so imported child inputs use the child port type at the call site, while imported and external outputs continue to drive live parent-bound wires.
- Updated Verilog snapshots and contract coverage to reflect the corrected boundary conversion behavior.

## 0.6.8

- Documented the ownership split for imported TENNCell modules and external RTL instances, including when parent-bound variables are wired through as live signals versus lowered to local state.
- Clarified that boundary conversions apply in both read and drive directions across imported modules and externals.

## 0.6.7

- Reorganized the example tree into `examples/simple/` and added new standalone, composition, and FPGA examples, including the new `ballistic_if`, `verilog_composed`, and `blink_if` cases.
- Tightened the backend and documentation contracts around Verilog external wiring, Python/Verilog `top.*` removal, and CSV newline handling.

## 0.6.6

- Refactored Webots contract tests to shared fixtures so CLI and parser coverage reuse the same YAML inputs.
- Expanded Webots parser and CLI contract coverage for invalid controller settings, binding validation, and special init values.
- Tightened the backend documentation to describe Python, Verilog, and Webots responsibilities more explicitly.

## 0.6.5

- Preserved YAML source locations in backend errors so Python, Verilog, and Webots construction-time failures can report originating file and line information.
- Removed the Python backend's stale external-module rejection and kept the simulation/runtime path aligned with the same YAML-loading error contract.

## 0.6.4

- Fixed the blink UART Verilog example so the external UART TX output now drives the top-level `uart_tx` port directly.
- Updated the Verilog external-output contract and fixtures to distinguish internal TENNCell bindings from direct top-level port wiring.

## 0.6.3

- Fixed Verilog external output wiring so external module outputs now feed TENNCell local state before being exported at the top level.
- Updated the Verilog fixtures and contract wording to match the corrected external-output behavior.

## 0.6.2

- Added structured YAML source-location tracking so loader and backend errors can report file and line information, including nested import failures.
- Refactored YAML location lookup into a dedicated index object and updated the Verilog and Webots section parsers to use it.

## 0.6.1

- Added inferred Verilog boundary ports for TENNCell child modules that omit `verilog.ports`, using the module's `verilog.real_encoding`.
- Tightened the Verilog YAML contract to require explicit `direction` fields and removed the legacy `dir` fallback.
- Kept generated Verilog files under `` `default_nettype none`` throughout and updated the Verilog fixtures, docs, and examples accordingly.

## 0.6.0

- Tightened the Verilog contract around `verilog.ports`, `verilog.externals`, and scalar `clock` / `reset` names.
- Removed the legacy mapping-style `clock` / `reset` form from the Verilog parser.
- Updated the public documentation, FPGA examples, and Verilog fixtures to the current contract.

## 0.5.0

- Add the Webots controller backend with binding-based device mappings and `init` support.
- Split YAML loading into raw parsing and resolved model assembly.
- Extend contract coverage to the Webots CLI/backend paths and keep CLI smoke tests on fixtures.

All notable changes to this project are documented here.

## [0.4.1] - 2026-06-01
- Fixed YAML loading so bang-prefixed expression scalars such as `!false` and `!(x > 1)` are treated as plain strings instead of YAML tags
- Added regression coverage for bang-prefixed expressions in YAML loader paths

## [0.4.0] - 2026-06-01
- Added contract-driven public API docs and reorganized the test suite around public, internal, functional, CLI, and coverage layers
- Moved examples to a repository-level `examples/` tree and grouped multi-file examples into dedicated folders
- Split YAML loading/lowering and Python/Verilog emission state into explicit per-run contexts for cleaner backend extension
- Clarified simulator compute/IO modes, Verilog YAML behavior, and library-versus-CLI usage in the documentation
- Added local lint, format, and typecheck tooling for development workflow support

## [0.3.7] - 2026-04-23
- Added load-time constant expression evaluation for ordered constants, allowing expressions such as `B: 3 * A + 1`
- Documented constant expression rules and added regression coverage for ordered references and invalid forward references

## [0.3.6] - 2026-04-16
- Added YAML `fsm:` sugar with support for multiple FSMs per module, namespaced generated state constants, and state-scoped rule lowering
- Added recursive YAML `if` / `then` / `else` sugar with single-item branch normalization and lowering to ordinary guarded rules
- Added runtime and Verilog coverage for FSM and recursive conditional lowering
- Added new examples for recursive conditionals and FSM-based TENNCell descriptions

## [0.3.5] - 2026-04-16
- Fixed Verilog fixed-to-logic vector output conversion so multi-bit logic top ports preserve bit patterns instead of collapsing to a boolean
- Fixed Verilog conversion helper naming for logic vectors to include width and avoid helper-name collisions when multiple logic output sizes are present
- Added regression coverage for logic vector conversion and mixed logic output widths in Verilog generation
- Added and refined Tang Nano 20K FPGA `ledwalk` example, including active-low LED behavior documentation (`0` means LED ON)

## [0.3.4] - 2026-04-16
- Fixed Verilog import/external connection lowering so unqualified local variable names are wired to generated local state signals instead of undeclared identifiers
- Fixed UART blink example generation where `toggle_pulse` import wiring could reference an undefined bare signal
- Added regression coverage for unqualified local-variable connection mapping in Verilog generation
- Documented the connection-lowering behavior in `rules.md`

## [0.3.3] - 2026-04-16
- Fixed `zero_reset_mode` so current-step input variables are preserved in the simulator and generated Python/Verilog backends instead of being zeroed
- Fixed Verilog external output bindings so connected top-level ports such as `uart_tx` are driven correctly
- Fixed Verilog helper-literal emission so conversion helpers always reference declared literal aliases
- Corrected the FPGA UART blink example generation path and added regression coverage for the related bugs

## [0.3.2] - 2026-04-16
- Fixed Verilog fixed-point signedness handling so `module.real_encoding.signed` controls fixed-point state, literals, constants, and helper typing
- Added regression coverage for unsigned fixed-point Verilog generation
- Clarified Verilog signedness behavior in the documentation

## [0.3.1] - 2026-04-16
- Added explicit Verilog boundary conversion for NNC inputs and outputs that share names with declared `top_ports`
- Made fixed-point to integer top-port conversion truncate toward zero
- Clarified README documentation for raw `top.*` signals versus local TENNCell variables at the module boundary
- Added FPGA-oriented examples under `examples/fpga/`, including standalone `blink.yaml`/`ledwalk.yaml` and foldered `blink_uart/`, `verilog_controller/`, `fpga_uart_led/`, `fpga_spi_gpio_bridge/`, and `axii/` examples

## [0.3.0] - 2026-04-16
- Added per-module `zero_reset_mode` to force zero-based recomputation of local variables each step
- Simplified Python and Verilog code generation for modules using zero-reset semantics
- Fixed Python CLI generation for imported systems so `-t python` emits a single composed file
- Clarified documentation around persistent outputs versus explicit reset rules
- Expanded tests for zero-reset mode and Python CLI import emission
- AI has been used to help with code-generation and refactoring work from this version onward

## [0.2.0] - 2026-04-16
- Added a Verilog/SystemVerilog backend with import-aware multi-file generation
- Added YAML support for `module`, `imports`, `externals`, `constants`, and `aliases`
- Added fixed-point Verilog lowering, generated conversion helpers, and literal aliases
- Added Python support for import-composed TENNCell systems in both the runtime simulator and generated single-file Python output
- Added examples, documentation, and rules tracking for schema and code-generation behavior
- Expanded test coverage for import resolution, Python composition, and Verilog generation

## [0.1.3] - 2025-10-08
- Improved error handling with cleaner error messages

## [0.1.2] - 2024-10-08
- Minor bug fixes and improvements
- Enhanced test coverage for transformers

## [0.1.0] - 2025-09-30
- Added Transformers and nnc-gen script
- Created a Python transformer
- Added comprehensive test suite for transformer functionality

## [0.0.6] - 2025-09-25
- Updated verification of cell id
- Improved CI: deploy to PyPI, doc/artifact generation


## [0.0.5] - 2025-09-24
- Finished 100% test coverage
- Added coverage reporting
- Added new functions and corresponding test coverage

## [0.0.4] - 2025-09-23
- Added CSV support in continuous mode

## [0.0.3] - 2025-05-08
- Updated version location

## [0.0.2] - 2025-05-06 (pyproject.toml)
- Switched to dynamic versioning in pyproject.toml
- Project structure improvements and versioning automation

## [0.0.1] - 2023-12-14 (pyproject.toml)
- Project initialization
- Introduced Value class and basic structure
- Initial CLI and test setup
