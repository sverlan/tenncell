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
- Source locations are indexed by the same resolved keys as the loaded data (for example a key written `010` is indexed as `10`, `true` as `True`), so errors about such keys point to the key's own line.
- Errors raised from imported YAML files must preserve the imported file path in the message.

## YAML Schema
- Plain (unquoted) YAML values are resolved with YAML 1.2 core-schema rules, plus two YAML 1.1 number forms. This affects only how values are interpreted; YAML syntax is unchanged.
  - `true`/`false` (any of `true True TRUE false False FALSE`) are booleans; `on`, `off`, `yes`, `no` in any capitalization are ordinary strings and can be used as names (for example FSM states `ON`/`OFF`).
  - `null`, `Null`, `NULL`, `~`, and an empty value mean "no value".
  - Integers are decimal (a leading zero is still decimal: `010` is 10), hexadecimal `0x...`, octal `0o...`, or binary `0b...`; underscores are allowed (`1_000`).
  - A number with a decimal point or an exponent is a float (`1e5`, `1.5e-3`); `.inf`, `-.inf`, and `.nan` are floats.
  - Dates, base-60 numbers such as `1:30`, and a bare `=` are ordinary strings.
- Boolean settings accept only `true` or `false`; any other value, including the strings `"false"`, `no`, or `off`, is rejected with the YAML line. This applies to `module.zero_reset_mode`, the Verilog `signed` fields, and `webots.csv.include_step`/`include_time`/`include_initial`.
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

## Include Fragments
- Root YAML files may declare `module.include` as a string path or list of string paths.
- Included files are YAML section fragments, not TENNCell module imports.
- Included files must be YAML mappings containing top-level sections such as `constants`, `aliases`, `cells`, `imports`, `rules`, `fsm`, `verilog`, or `webots`.
- Included files must not contain a `module` section; includes are non-recursive in v1.
- Include paths resolve relative to the root YAML file first, then through the caller's import paths.
- Includes are expanded before normal parsing, repeat lowering, backend metadata parsing, and semantic TENNCell imports.
- Included fragments are merged in listed order, then the root document is merged after removing `module.include`.
- Mappings merge recursively. Scalars must be identical or the loader raises a conflict error.
- Known list sections concatenate in merge order: `cells`, `imports`, `rules`, `fsm`, `verilog.ports`, `webots.csv.variables`, `verification.properties`, and `verification.backends.mc2.raw`.
- Includes do not create aliases, module boundaries, runtime child systems, Verilog submodules, or import connections. Use `imports` for semantic TENNCell module composition.

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
- The Python backend evaluates each guard and active production once in rule order against the current state, records variables consumed by active productions, initializes consumed next-state variables to zero, and then accumulates the stored productions in rule order.
- For the same inputs and deterministic expressions supported by the generated Python backend, generated Python `step()` produces results bitwise-identical to `NncSystem.step()`. Generated code must not use algebraically equivalent rewrites (such as adding productions to the old value and subtracting it afterwards) that change floating-point rounding.
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
- The MC2 transformer consumes the root module's TENNCell model plus its `verification` section. It emits MC2 query, ID, and trace-column files only; it does not generate traces or run MC2.
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
- The simulator and the `native` verification checker evaluate expressions with the same shared evaluator (`nnc.model.evaluation`): same operators, operand order, function-call order, and short-circuit `&&`/`||`; only the source of values differs.
- Python transformation emits one `.py` file for the full import closure, with internal helper classes plus one public root `NncSystem` wrapper.
- Generated Python supports every default function of the `MathFunctions` registry:
  - `pi` and `e` are emitted as `math.pi` and `math.e`;
  - `math` functions are emitted as `math.<name>(...)`;
  - `abs`, `min`, `max`, and `round` are emitted as Python built-ins;
  - `random()` is emitted as `random.random()`, and `import random` is added only when it is used.
- `random()` in generated Python is not seeded together with the simulator, so its draws are not expected to match `nnc-sim`.
- Functions registered at runtime through `MathFunctions.register_function`, including overrides of default function names, are rejected at generation time with an error naming the function, the rule, and the source file. Generated files stay standalone and do not import `nnc`.
- Python generation rejects documents with no model variables or semantic imports as having nothing to generate; this prevents external headers and include-only fragments from producing invalid empty classes.
- Qualified FSM state references such as `ctrl.ACTIVE` resolve to the lowered FSM state constant (`ctrl__ACTIVE`) in generated Python, as in the simulator and Verilog backend.
- Python composition executes imports in dependency order and keeps current float semantics at module boundaries.
- Generated Python scripts use the same CSV command-line behavior for standalone and composed systems.
- Generated Python scripts with input variables read CSV rows from standard input until exhaustion, do not require a `steps` argument, and exit with status `1` if a required input column is missing.
- Generated Python CSV output uses `lineterminator='\n'` so Windows stdout translation does not inject blank lines.
- Simulator compute mode emits JSON by default as a single array. The first object contains `"Message"` with the run summary. Following row objects contain `"Step"` plus the declared output variables as numeric JSON values.
- The simulator CLI uses the same CSV line-ending policy when writing CSV.
- CSV delimiter defaults to comma and applies to both CSV input and CSV output when a mode reads CSV.
- CSV precision defaults to no explicit numeric formatting; when set, numeric output values are formatted with that many decimal places.
- Initial CSV rows represent state before any executed step; after-step rows start at step `1`.
- Simulator IO-mode CSV preserves the output-variable-only column shape by default; `--csv-include-initial` does not add a `step` column.
- `nnc-sim --csv-include-step` prepends a `step` column to IO-mode CSV output. The optional initial row has `step` `0`, and after-step rows start at `1`. Compute-mode CSV always includes `step`, so the option changes nothing there.
- Autonomous CSV modes keep emitting an initial step `0` row by default and support `--csv-no-initial`.
- Input-driven CSV modes omit the initial row by default and support `--csv-include-initial`.
- Generated Python scripts without input variables require a `steps` argument.
- `zero_reset_mode` is per-module and does not propagate across imports.
- External Verilog modules are not part of the Python backend or runtime simulator configuration.
- Python backend and simulation-only errors should preserve the originating YAML file path and line number when source-location data is available.

## Verification
- A top-level `verification` section and verification backends (`native`, `mc2`, `sva`) are specified in `docs/verification.md`.
- The planned behavior becomes contractual only as implementation slices land; each slice adds its rules to this file.

### Verification Section Parsing
- `NncSystem.from_yaml()` ignores the `verification` section. It is parsed by `parse_verification_section()` on verification paths, which report errors with YAML file and line.
- `verification` must be a mapping with only the keys `environment`, `trace_semantics`, `properties`, and `backends`.
- `trace_semantics` is `strict` or `weak` and defaults to `strict`. A backend section may override it with its own `trace_semantics`.
- `environment` maps input names (strings; other YAML keys are rejected) to mappings with an optional `range: [lo, hi]` of numbers with `lo <= hi`. `distribution` is reserved and rejected.
- Accepted backend names are `native`, `mc2`, and `sva`. `prism`, `spin`, `english`, and `custom` are reserved and rejected; other names are rejected as unknown.
- Backend keys: `native` accepts `trace_semantics`; `mc2` accepts `trace_semantics` and `raw`; `sva` accepts `trace_semantics` and `mode` (`simulation`, `formal`, or `both`; default `simulation`).
- `native.raw` is rejected. `sva.raw` is rejected until the SVA backend is implemented.
- Each `mc2.raw` entry has a required identifier `id`, an optional string `description`, and a required string `code`. Raw IDs are unique within `mc2.raw`. Exactly one final newline is stripped from `code`.
- `properties` is a list of generic properties. Each has a required identifier `id` (unique among properties), and optional `description`, `targets` (backend names), and `from_step` (non-negative integer, default 0). Unknown keys are rejected; `probability` is reserved and rejected.
- The property kind is given by the exact set of kind keys: `always`; `never`; `eventually`; `eventually` + `within`; `when` + `then` + `after`; `when` + `then` + `within`; `when` + `then_always` (+ optional `after`, default 0); `cover`. Any other combination is rejected with a message naming the problem (for example `'when' + 'then' needs exactly one of 'after' or 'within'`).
- `after` is a non-negative integer and `within` is `[a, b]` with integers `0 <= a <= b`. Offsets count trace rows.
- Conditions are TENNCell guard expressions (or YAML `true`/`false`); nested properties are rejected. They are parsed against the model like rule guards, and every name must resolve: local variables, constants, aliases (to their target), FSM states (`ctrl.DONE`), and imported inputs/outputs (`sensor0.level`). Errors point to the condition's line.
- A qualified name that is both an FSM state and an imported input/output (an import alias and an FSM with the same name) is rejected as ambiguous, as for raw `${name}` placeholders.
- Conditions may call only unmodified built-in functions. `random()` is rejected because it is nondeterministic, and functions registered or overridden at runtime are rejected.
- Binding records, for each property, the trace columns its conditions read (trigger first, in first-use order; imported inputs/outputs as `alias__port`; constants and FSM states are not columns) and the functions it uses. Backends use this to check whether they support a property.
- Include merging concatenates `verification.properties` and `verification.backends.mc2.raw`.

### Verification Placeholders
- Raw verification code is a template: `${name}` marks a reference to the TENNCell model, `$${` emits a literal `${`, and all other text is passed through unvalidated.
- A placeholder name is an identifier, optionally followed by one `.member` part. An unclosed `${`, an empty `${}`, or an invalid name is an error.
- A name may refer to a local variable, a constant, an FSM state (`ctrl.DONE`, lowered to `ctrl__DONE`), an imported input or output (`alias.port`), or an alias. Aliases resolve to the variable or imported input/output they reference.
- All candidates are collected without priority. A name that matches nothing is an unknown-reference error; a name that matches more than one entity (for example a constant and a variable with the same name) is an ambiguous-reference error.
- `verification.environment` keys must be root input variables.
- Binding errors name the raw entry and point to the YAML line of its `code`.

### Native Checker
- `nnc.verification.generic_properties.native.check_properties()` checks generic properties on a finite `Trace` with the built-in `native` semantics; it is the semantic reference for other backends.
- A `Trace` has one label per row (an `int` or `float` step or time value) and one mapping of column values per row. It must be non-empty, labels must be finite and strictly increasing, and every row must have the same columns.
- Time is row position: `after`, `within`, and `from_step` count rows (as MC2's `X` counts rows). Labels are only used for reporting.
- Kinds, over rows `from_step..L-1`, where every trigger row opens its own obligation:
  - `always P` / `never P`: fail at the first violating row; otherwise pass (also when the range is empty).
  - `eventually P`: pass if P holds on some row; otherwise open at the end.
  - `eventually P within [a, b]`: P must hold on some row of `from_step+a..from_step+b`; a completed window without P fails at its last row, a window reaching past the end is open.
  - `when T then P after n`: P must hold on exactly row `t+n`; it fails at `t+n`, or is open if `t+n` is past the end.
  - `when T then P within [a, b]`: P must hold on some row of `t+a..t+b`; a completed window without P fails at `t+b`, a window reaching past the end is open unless P was already seen.
  - `when T then_always P after n`: P must hold on every row from `t+n` to the end. This is "hold throughout" under both semantics: rows past the end are never checked, so a trigger too close to the end passes.
  - `cover P`: `covered` if P holds on some row, else `not_covered`, under both semantics.
  - Properties with a trigger but no trigger row pass.
- Open obligations at the end of the trace fail at the last row under `strict` and are `pending` under `weak`. The property result is the worst of its obligations (`fail` > `pending` > `pass`); a failure reports the obligation with the earliest detection row, ties going to the earliest trigger, with both row positions and labels.
- `trace_semantics` defaults to the `native` backend's effective setting (its own override, else the global value); an explicit value other than `strict` or `weak` raises `VerificationError`.
- Properties whose `targets` exclude `native` are reported as `skipped`, and their columns are not required.
- A column used by a checked property must exist and hold finite values in every row; otherwise the check raises `VerificationError`. Errors while evaluating a condition (for example `sqrt` of a negative value) also raise `VerificationError`, naming the property, the condition role, the row, and the label. They are operational errors, never property failures.

### nnc-verify
- `nnc-verify MODEL.yaml (--trace FILE | --inputs FILE | --steps N)` checks the model's generic verification properties with the `native` checker. Exactly one of `--trace`, `--inputs`, `--steps` is required; a missing or second source, or an invalid argument value type, is a usage error with exit status `2`.
- `--steps N` simulates a model without inputs: trace row 0 is the initial state, followed by N steps (N+1 rows). It is an error for a model with inputs.
- `--inputs FILE` simulates a model with inputs: row 0 is the initial state, and input record k drives the transition to row k (N records give N+1 rows). The header must name each root input exactly once (unknown, missing, duplicate, or empty column names are errors). It is an error for a model without inputs.
- Simulated rows contain every local variable (internal variables included) and imported modules' inputs and outputs as `alias__port`.
- `--trace FILE` checks a recorded trace: the model's rules are not run; the model only supplies the properties, names, constant and FSM-state values, aliases, and required columns. A header line is required. If the first column is named `step`, `_step`, `time`, or `Time`, it gives the row labels; otherwise rows are labelled from `--first-step` (default 0). A step-named column that is not first is ordinary data.
- `--delimiter` (default comma) applies to `--trace` and `--inputs` files. It must be a single character; `" "` means any run of whitespace. Any other value is a usage error (exit `2`). Other delimiters use CSV parsing (quoted fields allowed); malformed CSV is an error with its line. Only blank or whitespace-only lines are skipped; a line of empty fields such as `,,,` is a data row and is validated.
- Only columns used by checked properties are read as numbers; other columns (and columns used only by skipped properties) are ignored. Empty or duplicate header column names, rows with a different number of fields, non-numeric used values or labels, non-increasing or non-finite labels, and an empty trace are errors with the file and line where known. When all labels are integral and an increment differs from 1, a warning is printed (offsets count rows, not steps). Integral labels (`3` or `3.0`) are reported as integers.
- Output is a table (`id`, `kind`, `result`, `trigger`, `reported`, `open`), or JSON with `--json` keeping every `PropertyResult` field and the statuses `pass`, `fail`, `pending`, `covered`, `not_covered`, and `skipped`.
- Exit status: `0` when no property fails (`pass`, `pending`, `covered`, `not_covered`, and `skipped` do not fail); `1` when a property fails or on an operational error (bad model or trace, missing column, a model without generic properties, an evaluation error); `2` for usage errors.

### MC2 Backend
- `nnc-gen -t mc2` generates MC2 query files from `verification.backends.mc2.raw` and the generic `verification.properties` of the root YAML file. It does not run MC2.
- For each root file it writes three files, each line ending with a newline:
  - `<stem>.mc2.pltl`: one rendered MC2 query per raw entry, in YAML order, then one per emitted generic property, in YAML order, with no comments;
  - `<stem>.mc2.ids`: the raw entry and property IDs, in the same order as the queries;
  - `<stem>.mc2.columns`: the trace columns the queries reference, in first-use order (raw entries first, no duplicates).
- `--output-suffix` is appended to `<stem>` for all three files.
- If nothing is emitted (no `mc2.raw` entries and no generic property for MC2), generation fails with "No MC2 verification entries found".
- Each raw entry must be exactly one non-empty single-line query after the final newline is stripped; YAML folded style `>-` joins long queries onto one line.
- Placeholders render as bare names; users write the MC2 brackets (`[${x}]`, `d[${x}]`, `max([${x}])`):
  - a local variable renders as its name and is listed in `.mc2.columns`;
  - an imported input or output `alias.port` renders as `alias__port` and is listed in `.mc2.columns`;
  - an alias renders as its target;
  - constants and FSM states render as numeric literals without exponent notation (`3`, `2.5`, `0.00001`) and are not listed as columns.
- Generic properties without `targets`, or whose `targets` include `mc2`, are translated to MC2; properties targeting only other backends are omitted silently.
- MC2 queries cannot call functions. A property with a function call is an error when its `targets` list `mc2`, and is otherwise skipped with the warning "generic verification properties skipped for MC2: <id> (calls <functions>; MC2 queries cannot call functions)".
- An emitted property ID equal to an `mc2.raw` ID is an error. The check runs after filtering, so a property not emitted for MC2 (for example `targets: [native]`) may share an ID with a raw entry.
- Each property becomes one `P=?[...]` query (translation table in `docs/verification.md` section 7.3). Conditions render with every binary operation parenthesized: variables as `[name]`, imported IO as `[alias__port]`, aliases as their target, constants and FSM states as numbers (negative ones as `(-n)`), `&&` as `^`, `||` as `V`, `!` as `¬(...)` (U+00AC), `==` as `=`, unary minus as `-(...)`. `->` is never emitted.
- `X^k` is k nested `X`; `¬X^k(true)` ("the trace ends within k rows") makes `from_step` past the end of the trace and the weak end-of-trace forms agree with `native`. A `within: [a, b]` window renders as `X^a(p V X(p V ... X(p)))`, linear in `b - a`.
- The MC2 query uses the `mc2` backend's effective `trace_semantics`. With `weak`, `nnc-gen` warns that MC2 counts obligations still open at the end of the trace as satisfied for bounded `eventually` and response properties whose obligations can stay open (an upper bound or delay above 0, or `from_step` above 0 for bounded `eventually`; native reports `pending`), and that MC2 checks unbounded `eventually` strictly (an unmet condition gives 0).
- `nnc-sim` traces contain only output variables. When a column in `.mc2.columns` is not a root output variable (an internal variable, a root input, or an imported input/output), `nnc-gen` prints a warning to stderr: "MC2 trace columns are not root outputs, so nnc-sim traces will not contain them: <columns>". Declaring a local variable as an output only exposes it and does not change simulation results.
- When the model has a `webots.csv` section, the Webots controller's CSV log is a second trace source: a column needs no warning if it is a root output or listed in `webots.csv.variables`. Columns in neither give the warning "MC2 trace columns are neither root outputs (nnc-sim traces) nor listed in webots.csv.variables (Webots CSV log): <columns>". `nnc-gen` also warns when `webots.csv.include_step` is false (MC2 reads the first column as time) or when `webots.csv.delimiter` is not a space, tab, or `;`.
- MC2 reads the first trace column as time, so MC2 traces from IO mode need `nnc-sim --csv-include-step`.
- MC2 v2.0beta2 accepts `^` (and), uppercase `V` (or), `->`/`=>` (implies), and the NOT sign U+00AC; `!` is only valid in `!=`. Raw MC2 code is passed through unchanged, so `nnc-gen` does not rewrite these operators.
- Opt-in functional tests run generated queries and `nnc-sim` traces through MC2, and check that MC2 agrees with `native` on generic properties (pass and covered give 1, fail and not_covered give 0, weak pending gives 1 except unbounded `eventually`, which gives 0), when `NNC_MC2_JAR` points to the MC2 jar and `java` is on `PATH`; otherwise they are skipped.
- `BaseTransformer.transform_files()` returns output files keyed by suffix; by default it emits one file from `transform()` and `get_file_extension()`. `nnc-gen` writes every returned file and prints transformer warnings to stderr.

## FPGA Examples
- The `examples/fpga/ledwalk.yaml` Tang Nano 20K example uses active-low LED semantics (`0` drives LED ON) and implements a walking-zero pattern on `leds[5:0]`.

