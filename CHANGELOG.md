# Changelog

## 0.10.1

- Webots controllers with a CSV log or `shutdown` code run their loop in `try`/`finally`: the log is closed and the `shutdown` code runs also after an error. `webots.code` file paths must be relative (an absolute path silently discarded the YAML file's folder). Transformer errors about bindings, `init` and the CSV list now name their YAML line. The Webots modules are type-checked (`pdm run typecheck`). Generated Python `step()` docstrings no longer have whitespace-only lines.
- Webots CSV logs: in the rows after a step, an input variable now holds the value the step received, as `nnc-verify --inputs` rows do. Before, an input consumed by a rule logged 0, so the log could not show sensor readings, and properties about inputs checked with `nnc-verify --trace` saw 0. The e-puck virtual-sensor example now logs its obstacle readings.
- Webots docs: `docs/webots_tutorial.md` (plain bindings, pasted code, methods added to devices, virtual devices, common mistakes) and the example `examples/webots/e_puck_virtual_sensors/`, an e-puck that avoids obstacles reading each side as one virtual device combining three proximity sensors, with clamped wheel speeds (checked in Webots' e-puck world).
- Webots: `webots.code` pastes user Python (inline or from a file relative to the YAML file) at fixed points of the generated controller: `module`, `setup`, `before_step`, `after_step`, `shutdown`, between marker comments, using documented controller names (`robot`, `devices`, `inputs`, `variables`, ...). Nothing is imported or run at generation. `setup` runs right after the devices are created, so it can add methods to them that bindings and `init` then call (for example an LED write converting the model's float to the int Webots expects). A `read_method`/`write_method` that is not a method name (an expression) is still pasted into the controller, now with a warning pointing to `webots.code.setup`; an empty value or a lone keyword is an error. A binding may leave out `device` for a virtual device that `setup` provides (an object combining sensors, computing a value or recording an output); the controller does not look it up and stops right after `setup` if it was not provided. Real device names are still looked up, so a typo still gets Webots' warning. Controllers now close their CSV log after the loop. Generated controllers are tested by running them in a small in-process Webots simulator, and in real Webots (opt-in `NNC_WEBOTS`).

## 0.10.0

- Completed the SVA user documentation and added runnable passing and failing examples under `examples/verification/`, covering monitor simulation, bounded checks, cover, proofs, unbounded-eventually liveness, BMC/cover witness replay, and native comparison.
- Formal SVA checks now include unbounded `eventually` as liveness: one `$live` cell for all of them in a helper module `<stem>_sva_live.v` and a `live` task in `<stem>.sby` (engine `suprove`, Linux oss-cad-suite; on Windows run it in WSL). The task removes the other assertions so that a failing safety property cannot make liveness pass vacuously. Previously these properties were skipped (mode `formal`) or simulation-only (mode `both`).
- `nnc-gen -t sva --sva-replay WITNESS.yw`: generates a self-checking replay of a SymbiYosys bmc counterexample or cover trace. The witness inputs become the testbench stimulus, the testbench reports whether the failure (or cover) is reproduced on the witness's row, and the decoded inputs let `nnc-verify` tell whether the model agrees or diverges (fixed point). `nnc-gen` does not run the simulator.
- Numbers as import connections and external-module input connections (`a: 5`, `a: -2.5`) now work: YAML numbers crashed reference validation, the Verilog backend wrote them raw (`.a(5)`, wrong in fixed point) instead of encoding them for the child's port, and decimals were taken for `alias.port` references. Booleans and other types are errors with their line, a number connected to an external module's output is an error, an explicit `null` external input drives 0, and an unknown plain name in an import connection is now reported when the model is loaded instead of at the first step.
- **Behavior change - imports reading other imports' outputs.** A step is now synchronous, as in numerical P systems and in the generated RTL: every import is given values of the configuration before the step, then all imports step. Before, imports were stepped in dependency order, so an import reading another import's output saw its new value of the same step; it now sees it one step later in `nnc-sim`, `nnc-verify` and the Python backend, which now agree with the generated Verilog. Imports may now read each other's outputs in a cycle (this was an error). Models without such connections are not affected; no example under `examples/` has one.
- **Correctness fix - simulation of a module imported twice.** Two imports of the same file shared one system object in `nnc-sim`, `nnc-verify` and the Python model, so stepping one instance also stepped the other and they shared their state. Each import is now its own instance, as in the generated Python and Verilog code.
- SVA properties and raw placeholders now read imported inputs through row-aligned checker copies. An imported input connected to a parent register therefore reports the value the child was given during the transition instead of the parent's post-edge register value.
- `nnc-verify`: an imported input column (`alias__port`) now holds the value the parent gave the child in the step that produced the row, also when the child consumed it, as root input columns do; before, such rows showed the consumed value (often 0). This matches the SVA checker's copies for imported inputs read from parent signals.
- `nnc-gen -t sva --sva-mode formal|both [--sva-depth D]`: formal checks with SymbiYosys. The checker gets assertions and covers for every generic property except unbounded `eventually` (liveness, added later), the reset scheme, and `verification.environment` ranges as assumptions on the input ports; `<stem>.sby` has the `bmc` and `cover` tasks over rows `0..D-1`, and the proof tasks `prove_kind` (k-induction) and `prove_pdr` (PDR) for runs of any length, helped by invariants of the monitor counters. Opt-in tests run SymbiYosys and lock the depth contract.
- `nnc-gen -t sva --sva-style concurrent`: generic properties as standard concurrent SVA (`assert property` / `cover property`, strong operators for strict semantics) for simulators with full SVA support. Every generated file is checked with slang (opt-in); Verilator 5 runs only the plain forms (`always`, `never`, zero-bound responses), as documented in `rules.md`.
- New `nnc-gen -t sva` (simulation): with `--sva-inputs FILE` (models with inputs) or `--sva-steps N` (without), it writes the RTL closure, the checker and a testbench `<stem>_tb.sv` that prints `nnc-verify`'s results for the generated RTL (`SVA_RESULT`/`SVA_OPEN` lines). Inputs are encoded for the RTL ports in `<stem>_inputs.hex`, and decoded back in `<stem>_inputs_decoded.csv` for `nnc-verify --inputs`. Options: `--delimiter`, `--skip-lines`, `--sva-source`, `--sva-max-bound`, `--sva-style`. Checked against `nnc-verify` in Icarus Verilog and Verilator (opt-in tests).
- `nnc-gen -t verilog` (and the SVA backend) now rejects model names that would be emitted as SystemVerilog keywords, such as a module named after a file `weak.yaml` or a port named `cover`, with an error naming what to rename. Before, the generated RTL did not parse.
- SVA backend groundwork: the checker now monitors every generic property kind (`always`, `never`, `eventually` with or without `within`, `cover`, and the `when` kinds `then ... after`, `then ... within`, `then_always`) in simulation and reports `native`'s results (`SVA_RESULT`/`SVA_OPEN` lines from the task `sva_report`), including trigger rows and open obligations. Conditions use the RTL's fixed-point encodings. Generation warns when the monitors would keep more than 65,536 bits of state. The generated files compile in Icarus Verilog (also with `FORMAL` defined) and pass a Verilator lint including the bind file (opt-in tests).
- **Correctness fix - regenerate RTL whose rules multiply or divide by a non-zero constant.** `nnc-gen -t verilog` emitted fixed-point products and quotients without rescaling: `x * 2` in Q8.8 multiplied by the encoded 512 and kept the low 16 bits, so it gave wrong values (0 for `x = 3` instead of 6); division by a constant had the same missing shift. Products are now computed in double width and shifted back by the fractional bits, and quotients shift the dividend first. No example under `examples/` is affected (the only product there multiplies by 0).
- `nnc-verify --inputs`: an input column now holds the input of the step that produced the row, as documented, also when a rule consumes the input (for example `u -> x` resets `u` to 0). Before, such rows showed `0`, so properties reading the input could pass or fail wrongly.
- SVA backend groundwork now emits the checker-module interface and formal bind file. Raw SVA placeholders use the selected RTL signals, root inputs use row-aligned checker copies, constants and FSM states use encoded Verilog literals, and the simulation reporting row counter is excluded from formal builds.
- `nnc-gen -t verilog` no longer silently loses a module when two modules of the import closure come from files with the same name in different folders (both were written to the same `.sv`, the second overwriting the first); this is now an error naming both sources. Names are compared case-insensitively.
- SVA backend groundwork (Python API, no `-t sva` yet): `SvaTransformer` and `SvaOptions` select which generic properties and raw SVA entries the backend can check against the generated RTL, and write the RTL closure. `verification.backends.sva.raw` is now accepted; `verification.backends.sva.mode` is rejected, because simulation or formal is chosen when generating, not in the model.
- **Correctness fix — regenerate RTL for designs with signed multi-bit `kind: logic` values.** Their registers were declared unsigned although the port and `signed: true` say signed, so SystemVerilog evaluated comparisons and arithmetic on them as unsigned: a register holding -1 did not satisfy `< 0`. Multi-bit logic storage now honors `signed` (`logic signed [W-1:0]`); one-bit signals stay unsigned.
- **Correctness fix — regenerate RTL for designs with multi-bit `kind: logic` output ports.** Such outputs were stored in their logic port encoding but converted on output as if they were fixed-point, i.e. shifted right by `frac_bits`: a counter on an 8-bit logic port read 0 instead of 3, and a 6-bit LED port initialised to 62 read 0. Output ports are now assigned from their source's actual encoding (directly when it equals the port encoding). Every module with a `kind: logic` output went through the faulty conversion; 1-bit outputs happened to keep the right value (the conversion tested `!= 0`), multi-bit outputs did not. Previously generated RTL for designs with multi-bit logic outputs, including FPGA examples, is wrong and must be regenerated. Among the examples, only `examples/fpga/blink_uart` was behaviorally affected: its UART driver sent byte 0 instead of `'0'`/`'1'` (48/49), checked in Icarus. The other examples with logic outputs use 1-bit outputs or `frac_bits: 0`, where the old conversion happened to keep the value; none were affected by the signedness or negative-literal fixes.
- Fixed Verilog generation of a parent output port driven by an imported module's output: the parent declared a second signal with the port's name and assigned the port twice, which Icarus rejects. The port is now assigned once, with the boundary conversion.
- Fixed Verilog generation of negative constants: they were written as `W'sd-N` (for example `16'sd-384`), which is not valid SystemVerilog, so any model with a negative constant or initial value failed to compile. They are now written as `-W'sdN`. An opt-in Icarus test (`NNC_IVERILOG`) compiles and simulates generated RTL.
- `VerilogTransformer.observe(system)` returns the TENNCell values observable in the generated RTL module (names, kinds, encodings and declared widths/signedness), built from the same emission context as the RTL. It is the basis of the upcoming SVA backend; the emitted RTL is unchanged.
- Fixed Verilog generation for renamed input ports (`verilog.ports.<input>.rename`): rules read the input through the TENNCell name, which is not declared in the module, so Icarus and Yosys rejected the RTL. They now read the renamed port.
- Fixed Verilog generation for imported modules with renamed ports: the parent connected the instance by the TENNCell port names, which the imported module does not declare. The instance is now connected through the renamed ports.

## 0.9.1

- `nnc-verify` reads PeP and Webots controller logs: `--no-step-column` labels rows by position when the step column is not a counter, `--skip-lines N` skips a preamble, and columns with an empty name (PeP's separator column) are ignored in `--trace` files. The error for non-increasing step labels suggests `--no-step-column`, and the gap warning no longer appears before that error.

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
