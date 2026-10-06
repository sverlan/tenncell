# Project Rules

## Change Documentation
- All future behavioral, schema, and code-generation changes must also be documented in this file.

## Project Naming
- The project and documentation name is `TENNCell`.
- `TENNCell` stands for Transformation and Execution of Numerical Networks of Cells.
- TENNCell is related to numerical P systems and generalizes many of their variants.
- The PyPI distribution is `tenncell`, and the CLI commands are `nnc-sim` and `nnc-gen`.
- The Python package is `nnc`, and its public system class is `NncSystem`.

## CLI Behavior
- `nnc-gen` processes all requested input files in batch mode.
- `nnc-sim --version` and `nnc-gen --version` print the command name and TENNCell version.
- If any requested input file is missing or any file fails to transform, the command still attempts remaining files but exits with status code `1`.
- If all requested files transform successfully, `nnc-gen` exits with status code `0`.
- YAML loader and transformer errors should include the originating YAML file path and line number when the parser has source-location data.
- Errors raised from imported YAML files must preserve the imported file path in the message.

## YAML Schema
- Standalone TENNCell YAML with top-level `cells` and `rules` remains valid.
- Top-level `name` and `description` are metadata only. They are ignored by Verilog generation.
- Optional top-level sections supported by the loader are:
  - `module`
  - `constants`
  - `aliases`
  - `imports`
  - `verilog`
  - `fsm`
- `cells` remains top-level for backward compatibility.
- `cells[].id` must be numeric.
- Variable names are module-level, not cell-local.
- A variable may be initialized only once in `cells[].contents`.
- Duplicate initial declarations in the same cell or across cells are rejected during YAML loading.

## Module Defaults
- If `module.name` is absent, the generated module name defaults to the source filename stem.
- If `module.zero_reset_mode` is absent, it defaults to `false`.
- `module.description` is allowed as ignored, comment-like metadata.
- The `module` section is optional; when absent, `module.name` defaults to the source filename stem and `zero_reset_mode` defaults to `false`.

## Verilog YAML Section
- Verilog-specific YAML configuration lives under the top-level `verilog` section.
- `verilog` must be a mapping.
- `verilog.real_encoding` is required for Verilog generation and must explicitly declare:
  - `kind`
  - `signed`
  - `width`
  - `frac_bits`
- If `verilog.clock` is absent, the clock name defaults to `clk`.
- If `verilog.reset` is absent, the reset name defaults to `rst` and reset is active high.
- `verilog.ports` describes the generated module interface for TENNCell input/output variables.
- Each `verilog.ports` entry must declare:
  - `direction`
  - `width`
- Each port may optionally declare:
  - `kind`
  - `signed`
  - `rename`
- `kind` defaults to `logic` when omitted.
- `rename` only affects the emitted Verilog port name.
- If `verilog.ports` is absent for a TENNCell module emitted to RTL, the Verilog backend infers a full module boundary from that module's TENNCell input/output variables and its `verilog.real_encoding` section.
- Inferred boundaries apply to the whole module; a module does not mix explicit `verilog.ports` declarations with inferred boundary ports.
- `verilog.externals` describes internal rewires to external modules.
- Each external instance may be declared either with:
  - `header`, `parameters`, `connections`
  - or `schema`, `parameters`, `connections`
- `verilog.externals` is mapping-only; each key is the instance alias.
- `header` points to a reusable external module description file.
- `schema` embeds the reusable external module description inline.
- External instances do not become part of the top-level module interface.
- `NncSystem.from_yaml()` does not parse the `verilog` section. Verilog section parsing is performed by the Verilog transform path and passed to the Verilog backend as backend configuration.
- External headers and inline schemas use a top-level `schema` section when describing reusable external module definitions.

### Verilog Internal Typing
- `verilog.types` is optional and applies only to TENNCell variables that are not already type-determined by a boundary binding.
- A local TENNCell variable that participates in an import or external connection inherits the effective Verilog type of that connected interface port.
- `verilog.types` does not override port, import, or external interface declarations.
- `verilog.types` may describe:
  - local state
  - local temporaries
  - internal control signals
- Each `verilog.types` entry may declare:
  - `kind`
  - `width`
  - `signed`
  - `frac_bits` when `kind` is fixed-point
- `kind: logic` covers Verilog bit-vectors; `width` is required and `signed` defaults to `false`.
- `kind: fixed_point` covers fixed-point encoded values; `width`, `frac_bits`, and `signed` are required.
- The Verilog backend uses `verilog.types` and interface-derived effective types for expression-domain selection, constant lowering, and internal signal declaration.
- When neither `verilog.types` nor a boundary binding determines a variable, the backend keeps the current inference behavior.

## Constants And Aliases
- `constants` are module-level numeric constants.
- `constants` may be literal numbers or constant expressions such as `A: 2 * 5` and `B: 3 * A + 1`.
- Constant expressions are evaluated during YAML loading, in declaration order, and may reference only previously declared constants.
- `constants` are read-only and are lowered as RTL `localparam` values.
- `aliases` are reference-only shorthands.
- `aliases` may point only to:
  - local variables
  - imported module IO references
- `aliases` do not support arbitrary expressions.

## Imports
- `imports` are explicit TENNCell module imports.
- Each import uses:
  - `module`: imported YAML file path
  - `as`: local alias
  - optional `connections`: structural connections for imported inputs
- Import resolution order is:
  1. relative to the importing YAML file
  2. CLI-provided import paths in order
- Import graphs must be acyclic.
- Imported module references allowed in expressions and guards are limited to declared imported inputs and outputs.

## Externals
- `verilog.externals` instantiate external RTL modules declared either by YAML headers or inline schemas.
- Each external uses:
  - `header` or `schema`
  - optional `parameters`
  - `connections`
- External headers and inline schemas use a top-level `schema` section and must declare ports explicitly.
- Supported external port kinds are:
  - `logic`
  - `fixed`

## Qualified References
- Supported reference forms are:
  - local variable: `x`
  - imported TENNCell IO: `sensor0.level`
- Qualified references are parsed directly by the TENNCell parser.
- Rule consumers must still be local variables in the current implementation.
- Declaring a variable as a cell `output` exposes it through the module interface only; it does not make the variable implicitly consumed, cleared, or recomputed each step.
- If `module.zero_reset_mode` is `true`, all local variables in that module are cleared to zero on every step before productions are accumulated, regardless of dynamic use.

## Structured Rule Sugar
- Top-level `rules` may contain:
  - plain rule strings
  - structured `{guard, producer, consumer}` rules
  - YAML `if` / `then` / `else` blocks
- `if` blocks are recursive and may appear anywhere a rule list is allowed.
- `then` is required; `else` is optional.
- Any rule-list field may be written as either a YAML list or a single rule item; the loader normalizes single items to one-element lists.
- Structured `if` blocks are pure syntactic sugar and are lowered into ordinary guarded rules during YAML loading.

## Repeat Sugar
- `repeat` is list-only YAML sugar for generating repeated core TENNCell items during YAML loading.
- In v1, `repeat` is supported only as a list item inside `cells[].contents`, `cells[].input`, `cells[].output`, and top-level `rules`.
- `repeat` is not supported directly in the top-level `cells` list, backend metadata, `imports`, `constants`, `aliases`, or `module`.
- A repeat item must define `var`, `range`, and `body`.
- `var` must match `[A-Za-z_][A-Za-z0-9_]*`.
- `range` is inclusive and must be `[start, end]` or `[start, end, step]`, with integer-only values.
- `step` defaults to `1`, cannot be zero, must match the range direction, and must reach `end` exactly.
- `body` must be a list and is spliced into the parent list once for every range value.
- Placeholders use `${name}`, `${name+K}`, or `${name-K}` where `K` is a positive integer literal.
- Exact scalar placeholders are lowered to integers; placeholders embedded in strings are replaced textually.
- Nested repeats are allowed, outer repeat variables are visible to inner repeats, and reusing an active repeat variable name is rejected.
- Repeat validation errors point to the original repeat block or invalid field where available; errors from generated items point to the repeat block/list that produced them.
- `repeat` is pure syntactic sugar and does not introduce arrays, runtime loops, or backend-specific generation behavior.

## FSM Sugar
- Top-level `fsm` is supported as YAML sugar for state-scoped rules.
- Multiple FSMs may exist in one module.
- Each FSM provides:
  - `name`
  - `variable`
  - `initial`
  - `states`
- Rules inside a state block are implicitly guarded by `fsm_variable == current_state`.
- FSM state names are local to one FSM and are lowered to generated namespaced constants such as `ctrl__IDLE`.
- FSM state constants may also be referenced with dotted sugar as `ctrl.IDLE`; the loader resolves that form to the lowered constant when it exists.
- FSM transitions are expressed by rules that write the FSM variable using one of that FSM's state names.
- If multiple active rules in one FSM state write the FSM variable in the same step, last rule in YAML order wins.
- FSM blocks are pure syntactic sugar and are lowered into ordinary constants, initialization, and guarded rules during YAML loading.

## Verilog Backend
- A `verilog` transformer exists alongside the Python transformer.
- The backend emits SystemVerilog-style RTL and writes one `.sv` file per TENNCell module in the import closure.
- Multiple cells inside one YAML file are flattened into a single Verilog module.
- The Verilog backend models consumption explicitly by zeroing used variables before accumulating productions.
- The Python backend keeps dynamic consume/rewrite behavior through the current `+ production - old_value` formulation after evaluating active rules.
- When `module.zero_reset_mode` is enabled, both Python and Verilog backends switch that module to zero-initialize all next-state values each step instead of using dynamic consume tracking.
- Imported TENNCell modules and external modules are instantiated structurally inside the generated Verilog module.
- Each generated Verilog/SystemVerilog file begins with `` `default_nettype none`` and keeps it in effect throughout the generated file.
- RTL parameters are emitted in the module header.
- Sequential logic uses `always_ff` and next-state logic uses `always_comb`.
- Fixed-point constants remain emitted as integer literals, with generated module-local `localparam` aliases such as `_VAL_1_0` used for readability instead of `real`-based helper functions.
- Fixed-point state declarations, helper function signatures, and fixed-point literals follow the module or boundary signedness instead of always being emitted as signed values.
- Generated literal aliases should be documented with comments showing their source values and fixed-point format.
- Boundary conversions are emitted through generated integer-only helper functions rather than `real`-based helpers.
- Generated conversion helper names include logic vector widths when needed (for example `logic_4`, `logic_6`) so multiple logic output sizes in one module do not collide.
- If a TENNCell input or output is described in `verilog.ports`, the Verilog backend treats that port declaration as the external boundary type and inserts automatic conversions between the local fixed-point encoding and the declared Verilog port representation.
- Fixed-point values converted to top-level integer ports are truncated toward zero.
- Constant lowering into the target expression domain is an optimization the Verilog backend may apply to keep comparisons and arithmetic typed without converting live boundary signals.
- In Verilog generation, TENNCell inputs and outputs remain owned by their TENNCell module.
- Top inputs are sources at the module boundary. Top outputs are sinks at the module boundary.
- TENNCell input variables are emitted as direct Verilog ports and are read directly in expressions instead of being mirrored through `state_*` storage.
- Imported TENNCell inputs consume parent values; imported TENNCell outputs drive parent values.
- External RTL inputs consume parent values; external RTL outputs drive parent values.
- Each boundary conversion compares source and target encodings and inserts a conversion whenever they differ.
- When a parent rule references an imported-output or external-output bound variable, the Verilog backend converts that boundary value back into the parent module encoding before emitting the expression.
- Imported-module input ports use the imported module's declared `verilog.ports` entry when available; if that module omits `verilog.ports`, the backend infers a full boundary from its TENNCell inputs and outputs together with its `verilog.real_encoding` section.
- Imported-module outputs are emitted as live wires in the parent module and assigned from the child outputs instead of being lowered to local state.
- External RTL outputs are emitted as live wires in the parent module and assigned from the external outputs instead of being lowered to local state.
- When an imported TENNCell module or external RTL instance reads a parent-owned TENNCell variable, the backend wires that variable through as a read path with automatic boundary conversion when needed.
- When an imported TENNCell module or external RTL instance drives a TENNCell variable through `imports[].connections` or `verilog.externals.connections`, that variable is emitted as a live wire in the parent module and assigned from the child or external output instead of being lowered to local state.
- `verilog.externals` connections are wiring-only and do not appear in TENNCell rule expressions as `alias.port` references.

### Verilog boundary contract

| Case | Semantic owner | Backend role | Conversion rule | Emission rule |
|---|---|---|---|---|
| Top input | Outside the module | Source boundary value | Convert from top port encoding to local encoding if needed | Read-only input, not local state |
| Top output | The module | Sink boundary value | Convert from local encoding to top port encoding if needed | Driven from local value or boundary-driven wire |
| Imported input | Parent module | Child consumes parent value | Convert from parent encoding to imported port encoding if needed | Pass parent value into child input |
| Imported output | Imported child | Child drives parent value | Convert from imported port encoding to parent encoding if needed | Parent sees a live wire, not stale state |
| External input | Parent module | External instance consumes parent value | Convert from parent encoding to external port encoding if needed | Pass parent value into external input |
| External output | External instance | External instance drives parent value | Convert from external port encoding to parent encoding if needed | Parent sees a live wire, not stale state |

## Webots Backend
- A `webots` transformer exists alongside the Python and Verilog transformers.
- The backend emits controller code only; it does not generate Webots world or PROTO files.
- Webots-specific YAML configuration lives under the top-level `webots` section.
- `webots` must be a mapping.
- `webots.controller_name` defaults to the YAML stem when omitted.
- `webots.timestep` is optional and must be an integer when provided.
- `webots.bindings` maps local TENNCell variable names to Webots devices.
- Each binding may specify:
  - `device`
  - optional `read_method`
  - optional `write_method`
- Each binding must define at least one method.
- `webots.init` is an optional mapping of local TENNCell variable names to one-time initialization values.
- `webots.init` values are emitted through the binding's `write_method`.
- `webots.csv` is an optional mapping that enables CSV logging from the generated controller.
- `webots.csv.file` is required when `webots.csv` is present and is emitted as the runtime file path passed to `open()`.
- `webots.csv.variables` is required when `webots.csv` is present and may list any local TENNCell variable.
- `webots.csv.include_step` and `webots.csv.include_time` are optional booleans that add `_step` and `_time` columns.
- `webots.csv.include_initial` is an optional boolean that writes an initial variable snapshot before the controller loop and defaults to `false`.
- `webots.csv.delimiter` is an optional non-empty string and defaults to `","`.
- `webots.csv.precision` is an optional non-negative integer or `null`; when absent or `null`, CSV values use default string conversion.
- Webots CSV `_step` values are state indices: optional initial rows use `_step = 0`, and after-step rows start at `_step = 1`.
- A binding may be referenced for input, output, both, or initialization only, depending on the TENNCell model and the configured methods.
- Webots emission consumes the resolved TENNCell model and does not require external header files.
- Each declared TENNCell input variable must have a Webots binding with a `read_method`.
- Each declared TENNCell output variable must have a Webots binding with a `write_method`.
- Each `webots.init` variable must have a binding with a `write_method`.
- Webots bindings are local to the generated controller and do not affect TENNCell parser alias resolution.
- Webots generation may embed import-composed Python TENNCell code, but it emits only one controller for the root YAML file.

## Backend Boundaries
- The Python runtime simulator and Python transformer consume TENNCell model semantics only. They support TENNCell imports and do not consume `verilog.externals`.
- The Verilog transformer consumes TENNCell model semantics plus the `verilog` section. It supports TENNCell imports, `verilog.ports`, and `verilog.externals`.
- The Webots transformer consumes TENNCell model semantics plus the `webots` section. It emits controller glue around generated Python TENNCell code and does not generate Webots world, PROTO, or RTL files.
- Backend-specific sections are not parser aliases and should not be referenced from ordinary TENNCell expressions unless that backend explicitly defines such references.

## Supported Verilog Expression Subset
- Supported:
  - constants
  - variables
  - qualified references
  - addition
  - subtraction
  - unary minus
  - constant multiplication
  - constant division
  - integer multiply/divide AST nodes
  - boolean comparisons `< <= > >= == !=`
  - boolean `&& || !`
- Rejected clearly:
  - generic function calls
  - variable-by-variable multiplication
  - non-constant division
  - arrays
  - unsupported node types

## Numeric Conversion Rules
- Each Verilog module uses its own `verilog.real_encoding`.
- Boundary conversions are inserted automatically in Verilog:
  - fixed -> fixed: rescale by the `frac_bits` delta, then resize
  - logic vector -> fixed: extend, then shift left by target `frac_bits`
  - fixed -> logic vector: arithmetic shift right by source `frac_bits`, then resize
  - logic -> fixed: map `0/1`, then scale if needed
  - fixed -> logic(1-bit): compare against zero
  - fixed -> logic(N-bit): shift right by source `frac_bits`, then truncate to N bits
- Signed/unsigned mismatch is rejected only for fixed-to-fixed boundaries in the current implementation.
- Boolean-true guards are emitted as straight-line code in Python and Verilog backends instead of generating redundant `if True` / `if (1'b1)` wrappers.
- Constant operands may be lowered in the target expression domain as an optimization.
- Preferred constant lowering is:
  - boolean targets: emit sized `logic` literals such as `1'b1`
  - packed logic-vector targets: emit sized numeric literals such as `8'd1`
  - fixed-point targets: emit fixed-point mnemonics such as `_VAL_1_0`
- Fixed-point mnemonics omit the encoding suffix when the constant matches the module `real_encoding`; add the encoding suffix only when the constant is emitted in a different encoding.
- Constant lowering is a code-generation optimization, not a semantic requirement; boundary ownership and boundary conversion rules remain unchanged.
- Verilog expression domain selection follows these rules:
  - for `x == 1`, `x != 0`, and similar boolean comparisons with one constant, use the non-constant operand type and cast the constant to that type
  - for `x + 1`, `x - 1`, and similar arithmetic with one constant, use the non-constant operand type and cast the constant to that type
  - for `a + b` where both operands share the same type, use that common type
  - for `a + b` where one operand is fixed-point and the other is numeric, use the fixed-point domain and promote the numeric operand if needed
  - for `a + b` where both operands are fixed-point but differ in encoding, choose a common fixed-point domain and convert operands as needed
  - for mixed non-constant arithmetic, use the promoted operator type
  - for top/import/external boundary inputs and outputs, use the target port or parent type and apply conversion only at the boundary

## Python Backend And Simulator
- Existing standalone YAML files continue to work with the Python backend and simulator.
- Imported TENNCell modules are supported by the Python backend and runtime simulator.
- Python transformation emits one `.py` file for the full import closure, with internal helper classes plus one public root `NncSystem` wrapper.
- Python composition executes imports in dependency order and keeps current float semantics at module boundaries.
- Generated Python scripts use the same CSV command-line behavior for standalone and composed systems.
- Generated Python scripts with input variables read CSV rows from standard input until exhaustion, do not require a `steps` argument, and exit with status `1` if a required input column is missing.
- Generated Python CSV output uses `lineterminator='\n'` so Windows stdout translation does not inject blank lines.
- Simulator compute mode emits JSON by default as a single array. The first object contains `"Message"` with the run summary. Following row objects contain `"Step"` plus the declared output variables as numeric JSON values.
- The simulator CLI uses the same CSV line-ending policy when writing CSV.
- CSV delimiter defaults to comma and applies to both CSV input and CSV output when a mode reads CSV.
- CSV precision defaults to no explicit numeric formatting; when set, numeric output values are formatted with that many decimal places.
- Initial CSV rows represent state before any executed step; after-step rows start at step `1`.
- Simulator IO-mode CSV preserves the output-variable-only column shape; `--csv-include-initial` does not add a `step` column.
- Autonomous CSV modes keep emitting an initial step `0` row by default and support `--csv-no-initial`.
- Input-driven CSV modes omit the initial row by default and support `--csv-include-initial`.
- Generated Python scripts without input variables require a `steps` argument.
- `zero_reset_mode` is per-module and does not propagate across imports.
- External Verilog modules are not part of the Python backend or runtime simulator configuration.
- Python backend and simulation-only errors should preserve the originating YAML file path and line number when source-location data is available.

## FPGA Examples
- The `examples/fpga/ledwalk.yaml` Tang Nano 20K example uses active-low LED semantics (`0` drives LED ON) and implements a walking-zero pattern on `leds[5:0]`.

