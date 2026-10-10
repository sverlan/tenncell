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
- `rename` only affects the emitted Verilog port name; rules that read a renamed input read it through the renamed port, and a parent module connects an imported module through the imported module's renamed ports.
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
- Known list sections concatenate in merge order: `cells`, `imports`, `rules`, `fsm`, `verilog.ports`, `webots.csv.variables`, `verification.properties`, `verification.backends.mc2.raw`, and `verification.backends.sva.raw`.
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
- The backend emits SystemVerilog-style RTL and writes one `.sv` file per TENNCell module in the import closure. Two modules whose source files share a name (for example `a/controller.yaml` and `b/controller.yaml`) would be written to the same file; generation fails with an error naming both sources, and nothing is written for that model. File names are compared case-insensitively (`Controller.sv` and `controller.sv` collide), because they are the same file on Windows and macOS and generated RTL may move between systems.
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
- Negative signed literals are emitted as `-W'sdN` (for example `-16'sd384`), never as the invalid `W'sd-N`.
- Fixed-point state declarations, helper function signatures, and fixed-point literals follow the module or boundary signedness instead of always being emitted as signed values.
- `signed` controls SystemVerilog signed interpretation everywhere it applies: ports, boundary wires, and internal storage (`state_<name>` registers and conversion helper results). Multi-bit `kind: logic` signals with `signed: true` are declared `logic signed [W-1:0]`, so comparisons, extension, shifts and arithmetic on them are signed; one-bit signals are always declared unsigned.
- Generated literal aliases should be documented with comments showing their source values and fixed-point format.
- Boundary conversions are emitted through generated integer-only helper functions rather than `real`-based helpers.
- Generated conversion helper names include logic vector widths when needed (for example `logic_4`, `logic_6`) so multiple logic output sizes in one module do not collide.
- If a TENNCell input or output is described in `verilog.ports`, the Verilog backend treats that port declaration as the external boundary type and inserts automatic conversions between a signal's actual internal encoding and the declared Verilog port representation; a local output's register already uses its port encoding, so it needs no conversion.
- Fixed-point values converted to top-level integer ports are truncated toward zero.
- A top-level output port is assigned from its source signal (the `state_<name>` register, or a wire driven by an imported or external output), converted from that source's actual encoding to the port encoding; when the encodings are equal (for example a register stored in its `kind: logic` port encoding), the port is assigned the signal directly (`assign x = state_x;`).
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
- If that variable is a top-level output port, no separate wire is declared: the port itself is assigned once from the child or external output, with boundary conversion, and rules read the port (under its `rename` if set).
- `verilog.externals` connections are wiring-only and do not appear in TENNCell rule expressions as `alias.port` references.
- `VerilogTransformer.observe(system)` returns the TENNCell values observable in the module that `transform(system)` emits (`VerilogObservation`): clock and reset names, reset polarity, and one read-only `ObservedSignal` per root variable, imported output (`alias.port`, the `alias__port` wire) and imported input (the expression the parent drives into it). Each signal records its RTL expression, kind (`state`, `input_port`, `binding_wire`, `import_wire`, `import_input`), encoding, width and signedness **as declared in the RTL**, whether the expression is a declared signal (`connectable`), and the TENNCell initial value for root/imported inputs that require row-aligned copies. Names and declarations come from the same emission context and helpers as the RTL, so they always match it; observing does not change the emitted RTL.

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
  - optional `device` (see real and virtual devices below)
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
- Webots errors the transformer finds (unknown variables in bindings, `init` or the CSV list, missing bindings or methods, a virtual device without `setup` code) start with the YAML location of the binding, `init` entry or CSV list concerned (`file:line: `); a missing binding points to `webots.bindings`.
- Generated controller order: create the robot and one device per binding (`robot.getDevice`; Webots returns one object per device name), run the `setup` code (when given), call `enable(timestep)` on input devices that have it, write the `init` values once, open the CSV log (and write the initial row when configured), then loop `while robot.step(timestep) != -1`: read every input through its `read_method` (converted with `float`), `nnc.step(inputs)`, take the post-step variables, write the CSV row, and write every output through its `write_method`. With a CSV log or `shutdown` code, the loop runs in `try`/`finally`: the CSV file is closed and the `shutdown` code runs when the loop ends and also after an error, which is then raised again (when there is no CSV log, the `finally` block starts with `pass`, since the pasted code may be only comments). Controllers with neither keep the plain loop. Reads therefore see the state after the physics step, and writes take effect at the next one. In a row after a step, an input variable holds the value that step received (after any `before_step` code), as `nnc-verify --inputs` rows do, also when a rule consumed it (its post-step value is then 0); every other variable holds its post-step value. The initial row holds the initial values.
- `webots.code` is an optional mapping of user Python code pasted into the controller at fixed insertion points: `module` (top level, after the embedded model code, before `def main()`: imports, helper functions, constants), `setup` (right after the devices are created, before `enable`, the `init` writes, the CSV setup and the loop), `before_step` (in the loop, after the input reads, before `nnc.step`), `after_step` (after the step, the post-step variables and the CSV row, before the output writes) and `shutdown` (in the `finally` block after the loop, after the CSV close: also after an error). Other keys are errors with their YAML line.
- Each insertion point takes inline text or `{file: PATH}`; `PATH` is relative to the YAML file that declares it (an include fragment's own folder for code declared in a fragment); an absolute path, or one with a drive or root (`C:/x.py`, `/x.py`), is an error. `nnc-gen` reads the file as UTF-8 and pastes it; it never imports, copies or runs it. A missing or unreadable file, an empty path, or another value type is an error with the YAML line.
- Code is dedented (relative indentation kept), leading and trailing blank lines are dropped, and it is re-indented to its insertion point between `# webots code: <point> (<inline|PATH>)` and `# end webots code: <point>` comments; a point whose code is empty or whitespace is omitted. Code is not parsed or checked: it is trusted user code, and a syntax error shows when the controller runs.
- Names the code may use. `module` code runs at top level: it sees what it defines and the controller's module names (`Robot`, `NncSystem`, and `csv`/`format_csv_value` with a CSV log), not the names of `main()`. The other points run inside `main()` and see `robot`, `timestep`, `devices` (keyed by binding variable), `nnc` (the model instance) and the `module` definitions; in the loop also `inputs` (`before_step`, models with inputs: the dict then passed to `nnc.step`, so changes are what the model receives) and `variables` (`after_step`: the post-step variables; the CSV row is already written, so changing them affects only the output writes that follow). Rebinding these names, or `return`/`break` in the code, changes the controller; this is not prevented.
- Code files are read as UTF-8; a leading BOM is dropped.
- Real and virtual devices are kept apart:
  - a real device (`device: ps0`) is looked up with `robot.getDevice` as before; a wrong name still produces Webots' own "Device ... was not found" warning, so typos are not hidden;
  - a virtual device leaves `device` out: the binding is provided by user code. The controller does not call `getDevice` and puts `None` in `devices['x']`; `webots.code.setup` must replace it with any object that has the binding's methods (it can combine real devices, compute values, or record outputs). Without any `setup` code such a binding is an error at generation; if `setup` runs but leaves `devices['x']` as `None`, the controller stops right after `setup`, before the loop, with `Webots binding 'x' has no device: webots.code.setup must set devices['x']`. `enable` is called only on objects that have it (the existing `hasattr` guard), and `device: null`, an empty string or another non-string value is an error (only leaving the key out means virtual). `init` writes go through virtual devices too, since `setup` runs first.
- `read_method` and `write_method` are meant to be Python method names (identifiers, not keywords). Other text (an expression, for example `getValue and (lambda: ...)`) is still pasted after `devices['x'].` unchecked, with a warning naming the YAML line and pointing to `webots.code.setup`; an empty value or a lone keyword is an error. To read or write in another way, `setup` code adds a method to the device object and the binding names it (Webots device objects are plain Python objects), for example `devices['led'].set_int = lambda value: devices['led'].set(int(value))` with `write_method: set_int` (a Webots LED takes an int, the model gives floats). Because `setup` runs before `enable`, the `init` writes and the loop, added methods serve all of them.
- The `write_method` is called with the model's float value; a Webots device whose method needs another type (for example `LED.set`, which takes an integer) is not adapted by the backend.

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
  - model names that would be emitted as SystemVerilog keywords (IEEE 1800-2017): the module name (for example a file `weak.yaml` without `module.name`), port names (including `rename`, clock and reset), constant names, import and external aliases, the module and port names of imported modules (the parent instantiates them by name), and variables emitted as wires; the error names the keyword and what to rename. Names inside external module headers (module, ports, parameters) describe existing HDL and are not checked
- In a fixed-point encoding with `F` fractional bits and width `W`, a product of two values is computed in `2W` bits, shifted right (arithmetic) by `F` and cast to `W` bits: `W'((2W'(a) * 2W'(b)) >>> F)`. A quotient shifts the dividend left by `F` in `2W` bits first: `W'((2W'(a) <<< F) / 2W'(b))`. The shift rounds a product toward minus infinity; the division truncates toward zero. In a logic (integer) encoding, `*` and `/` are emitted unchanged.

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
- Each import is a separate instance with its own state, also when several imports load the same file.
- A step is synchronous (numerical P system semantics): every import is given values of the configuration before the step, including other imports' outputs, before any import steps. An import reading another import's output therefore sees it one step later, and imports may read each other's outputs in a cycle. This holds for `nnc-sim`, `nnc-verify`, the Python backend (which keeps current float semantics at module boundaries) and the generated RTL. Root input values given to `step` are written into the configuration first, as the environment's contribution to the step: a child connected to a root input receives that step's record, like the parent's rules.
- A connection that drives an input (`imports[].connections`, and `verilog.externals[].connections` of external input ports) is a variable, a constant, an imported output (`alias.port`), or a number. YAML numbers (`5`, `-2.5`) are accepted and stored as their decimal text; numbers are recognized before references, so `2.5` is a value. An empty connection (`null`) drives 0. In the RTL a number is encoded for the receiving port like a constant (fixed point scaled, logic as an integer, one bit as `1'b0`/`1'b1`). A connection of an external output port names the variable it drives; a number there is an error. Booleans, lists, non-finite or too large numbers are errors with their line, and a plain name in an import connection that is neither a variable nor a constant is an error when the model is loaded.
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
- Backend keys: `native` accepts `trace_semantics`; `mc2` and `sva` accept `trace_semantics` and `raw`.
- `native.raw` is rejected. `backends.sva.mode` is rejected: simulation or formal is chosen when generating (`nnc-gen -t sva --sva-mode`), not in the model.
- Each `mc2.raw` entry has a required identifier `id`, an optional string `description`, and a required string `code`. Raw IDs are unique within `mc2.raw`. Exactly one final newline is stripped from `code`.
- `properties` is a list of generic properties. Each has a required identifier `id` (unique among properties), and optional `description`, `targets` (backend names), and `from_step` (non-negative integer, default 0). Unknown keys are rejected; `probability` is reserved and rejected.
- The property kind is given by the exact set of kind keys: `always`; `never`; `eventually`; `eventually` + `within`; `when` + `then` + `after`; `when` + `then` + `within`; `when` + `then_always` (+ optional `after`, default 0); `cover`. Any other combination is rejected with a message naming the problem (for example `'when' + 'then' needs exactly one of 'after' or 'within'`).
- `after` is a non-negative integer and `within` is `[a, b]` with integers `0 <= a <= b`. Offsets count trace rows.
- Conditions are TENNCell guard expressions (or YAML `true`/`false`); nested properties are rejected. They are parsed against the model like rule guards, and every name must resolve: local variables, constants, aliases (to their target), FSM states (`ctrl.DONE`), and imported inputs/outputs (`sensor0.level`). Errors point to the condition's line.
- A qualified name that is both an FSM state and an imported input/output (an import alias and an FSM with the same name) is rejected as ambiguous, as for raw `${name}` placeholders.
- Conditions may call only unmodified built-in functions. `random()` is rejected because it is nondeterministic, and functions registered or overridden at runtime are rejected.
- Binding records, for each property, the trace columns its conditions read (trigger first, in first-use order; imported inputs/outputs as `alias__port`; constants and FSM states are not columns) and the functions it uses. Backends use this to check whether they support a property.
- Include merging concatenates `verification.properties`, `verification.backends.mc2.raw` and `verification.backends.sva.raw`.

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
- `--inputs FILE` simulates a model with inputs: row 0 is the initial state, and input record k drives the transition to row k (N records give N+1 rows). The input columns of row k hold record k, also when a rule consumed (reset) the input variable in that step, as documented in `docs/generic_properties.md` section 5.2. The header must name each root input exactly once (unknown, missing, duplicate, or empty column names are errors). It is an error for a model without inputs.
- Simulated rows contain every local variable (internal variables included) and imported modules' inputs and outputs as `alias__port`. An imported input holds the value the parent gave the child in the step that produced the row (row 0: its initial value), also when the child consumed it, like a root input.
- `--trace FILE` checks a recorded trace: the model's rules are not run; the model only supplies the properties, names, constant and FSM-state values, aliases, and required columns. A header line is required. If the first column is named `step`, `_step`, `time`, or `Time`, it gives the row labels; otherwise rows are labelled from `--first-step` (default 0). A step-named column that is not first is ordinary data. `--no-step-column` labels rows by position even when the first column is step-named; that column is then ordinary data (for logs whose step column is not a counter, such as a constant Webots time step).
- `--delimiter` (default comma) applies to `--trace` and `--inputs` files. It must be a single character; `" "` means any run of whitespace. Any other value is a usage error (exit `2`). Other delimiters use CSV parsing (quoted fields allowed); malformed CSV is an error with its line. Only blank or whitespace-only lines are skipped; a line of empty fields such as `,,,` is a data row and is validated. `--skip-lines N` (default 0, a non-negative integer, otherwise a usage error) skips the first N lines of `--trace` and `--inputs` files, such as a PeP preamble; reported line numbers still count every line of the file.
- Only columns used by checked properties are read as numbers; other columns (and columns used only by skipped properties) are ignored. In a `--trace` file, columns with an empty header name (such as PeP's separator column) are ignored; `--inputs` files reject them. Duplicate column names, rows with a different number of fields, non-numeric used values or labels, non-increasing or non-finite labels, and an empty trace are errors with the file and line where known; the error for step-column labels that are not strictly increasing suggests `--no-step-column`. When the labels are valid, all integral, and an increment differs from 1, a warning is printed (offsets count rows, not steps). Integral labels (`3` or `3.0`) are reported as integers.
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

### SVA Backend
- Command line: `nnc-gen MODEL.yaml -t sva [--sva-mode simulation|formal|both] [--sva-style monitor|concurrent] [--sva-inputs FILE | --sva-steps N | --sva-replay WITNESS.yw] [--delimiter D] [--skip-lines N] [--sva-depth D] [--sva-source FILE]... [--sva-max-bound N] [-o DIR]`. Simulation and `both` need exactly one stimulus (`--sva-inputs`, `--sva-steps` or `--sva-replay`); `formal` takes none (giving one is an error for that file). `--sva-depth` applies to `formal` and `both` (default 20 rows); the concurrent style is for simulation only. Any `--sva-*` option, `--delimiter` or `--skip-lines` with another target, `--sva-inputs` together with `--sva-steps`, `--delimiter`/`--skip-lines` without `--sva-inputs`, and `--output-suffix` are usage errors (exit `2`). Without `--sva-replay`, a model with inputs needs `--sva-inputs` and a model without inputs `--sva-steps`; the wrong one, or none, is an error for that file (exit `1`) and nothing is written for it. `--sva-replay` works for both kinds of model.
- Python API: `nnc.transformers.SvaTransformer(options, verilog_configs, verification_configs, stimulus=None)`; `generate(system)` returns an `SvaOutput` (files, selection, warnings), `write(output, out_dir)` writes it. Without a `SvaStimulusSource` no testbench is generated.
- Writing removes this model's SVA-specific files that the run does not produce (`<stem>_sva_bind.sv`, `<stem>_sva_live.v`, `<stem>_tb.sv`, `<stem>_inputs.hex`, `<stem>_inputs_decoded.csv`, `<stem>.sby`), so a file of an earlier run (for example the stimulus of an earlier `--sva-inputs` run before a zero-record one) does not linger.
- `SvaOptions` (`nnc.verification.sva`) holds the execution choices: `mode` (`simulation` default, `formal`, `both`), `style` (`monitor` default, `concurrent`), `depth` (formal only; default 20 rows), `sources` (external RTL files) and `max_bound` (default 1024). A depth in simulation mode, a non-positive depth or bound, and the concurrent style outside simulation mode are rejected.
- The generated files include the RTL closure, one `.sv` per module, exactly as `nnc-gen -t verilog` writes it. A file-name collision between modules is an error, as for `nnc-gen -t verilog`.
- Generic properties without `targets`, or listing `sva`, are emitted. One the backend cannot check is an error when it lists `sva` and is skipped with a warning otherwise: a function call; a condition the RTL cannot express (variable-by-variable multiplication, general division); a value that is not a plain RTL signal (for example an imported input driven through a conversion); `after`, the upper `within` bound or `from_step` above the bound limit. Properties targeting only other backends are omitted silently.
- An emitted property ID equal to an `sva.raw` ID is an error; a property not emitted for SVA may share an ID with a raw entry.
- The concurrent style is rejected with `trace_semantics: weak` (effective for the `sva` backend).
- Raw entries (`backends.sva.raw`) may span several lines. Each variable or imported-port placeholder must name a plain signal of the generated RTL (state register, port or wire); constants and FSM states render as encoded literals.
- Nothing to emit (no generic property and no raw entry) is an error.
- External RTL sources (`sources`) are checked before anything is written (a missing file or two files with the same name, compared ignoring case, is an error) and copied into `<out>/sva_sources/` (not created without sources), overwriting files with the same names; files left there by an earlier generation are not removed. Relative `` `include `` paths inside copied sources are not supported. When the RTL instantiates `verilog.externals` and no source is given, a warning says so.
- The checker shell is `<module>_sva` and has the configured clock/reset plus one input port per distinct RTL signal read by an emitted property or raw entry. Root and imported input references use checker copy registers initialized to their own encoded TENNCell initial values; the copies update after each sampling edge, so row `k` reads the value that produced row `k`. Copies are distinct by TENNCell reference even when, for example, a root input and an imported input share one RTL signal, because their row-0 initial values may differ. A 64-bit `sva_row` counter used for simulation reporting is guarded by `` `ifndef FORMAL ``. Raw SVA entries are inserted at checker-module scope between ID comments; signal placeholders render as checker-visible signals (root and imported inputs use their copies), and constants/FSM states render as sized literals in the module's `verilog.real_encoding`.
- Simulation output contains the checker but no bind file. Formal or combined output also contains `<stem>_sva_bind.sv`, whose explicit named connections bind the checker to the selected signals in the generated module scope, and `<stem>.sby`.
- Formal checks (monitor style, modes `formal` and `both`): the checker has a `` `ifdef FORMAL `` block, without any result diagnostics: a register initialized to 1 and cleared at the first edge, with `assume (<reset active> == <register>)`, so the reset is active in the initial state, applied at the first edge and never again (row 0 is the first edge after it); one `always @(*) assume` per root input with an `environment` range, on the live input port; and in one `always @(posedge <clock>)` block, while the reset is inactive, one labelled immediate statement per property: `sva_<id>_check: assert (!<violation>)`, or `sva_<id>_cover: cover (<hit>)` for `cover`. The violation and hit signals are the monitors' combinational signals, so formal checks use the same history as simulation. An unbounded `eventually` is a liveness check instead: it is satisfied once its `seen` flag (set on rows `>= from_step` where the condition holds) or the current hit is true. All these properties share one instance `<module>_sva_live sva_liveness (.a(<conjunction of the satisfied signals>), .en(<reset inactive>))` of a helper module in `<stem>_sva_live.v` holding a Yosys `$live` cell (once `en` is true, `a` must eventually be true): `suprove` checks only the first liveness property of a model, and since every flag is sticky the conjunction eventually holds exactly when each property is eventually satisfied. The helper is generated only when there is such a property; slang cannot express `$live`, so it is read with `read_verilog -formal -icells` before `read_slang`. Its module name must not be a module of the RTL.
- Formal semantics (no `strict`/`weak` distinction; an obligation that would complete after the explored rows is not checked): `always`/`never`: every row `>= from_step`; `eventually within [a, b]`: at row `from_step + b` unless the condition held from row `from_step + a`; `when T then P after n`: at age `n` of each trigger; `within [a, b]`: at age `b` of each trigger, unless satisfied from age `a`; `then_always P after n`: every row from age `n` of the first trigger; `cover`: a `cover` objective (rows `>= from_step`); unbounded `eventually P`: on every infinite run from the reset, `P` holds on some row `>= from_step` (liveness; only the `live` task checks it, `bmc` and the proofs ignore it).
- Environment ranges become assumptions in the port encoding, rounded inward: fixed point `ceil(lo * 2^frac_bits)` .. `floor(hi * 2^frac_bits)`, logic `ceil(lo)` .. `floor(hi)`, intersected with the values the port can hold. A range clipped by the port gives a warning; a range with no port value, a non-finite range, or an input that is not an RTL port is an error.
- `<stem>.sby` (SymbiYosys) has the tasks `bmc` and `cover` (engine `smtbmc`), `prove_kind` (k-induction, engine `smtbmc`, induction length = engine depth) and `prove_pdr` (engine `abc pdr`), with `multiclock off`. It reads the RTL closure, the checker, the bind file and the copied sources with the yosys-slang front end (`plugin -i slang`, `read_slang -D FORMAL ... --top <module>`, because the built-in Verilog front end ignores `bind`), then `prep -top <module>` and `async2sync`. Depth contract: `--sva-depth D` explores rows `0..D-1`; the engine depth is `D + 2` (the reset step, and an immediate assertion in a clocked block reports one step after the row it checks). An obligation completing at row `D-1` is checked; one completing at row `D` or later is not. The `[files]` section lists the files by path, and SymbiYosys copies them by name, so an `--sva-source` file named like a generated file is an error, and so is a file name with whitespace (the `.sby` lists names unquoted) among the RTL closure, the checker and the sources. Proofs cover every assertion at once and hold for runs of any length: one false property makes them fail (`bmc` names it). Only PASS means proved; k-induction answers UNKNOWN when the induction length is shorter than the history a monitor keeps (the largest `after`/`within` bound, or `from_step` plus a window), which a larger `--sva-depth` or PDR resolves. To keep unreachable monitor states out of induction proofs, the checker also asserts invariants under `FORMAL`: the step counter is at most its limit, and a `then_always` age counter is at most `after` and 0 until the first trigger. With an unbounded `eventually`, the `.sby` has a fifth task, `live` (mode `live`, engine `aiger suprove`, no depth: the other tasks get `~live: depth`): SymbiYosys would turn the other assertions into assumptions in live mode, so a failing safety property could leave no run and make liveness pass vacuously; the script removes them for this task (`live: chformal -assert -remove`) and keeps the assumptions. The task reports one status for all liveness properties (FAIL names none of them: check one property at a time to find it) and no trace (`--sva-replay` does not apply). `suprove` ships with the Linux oss-cad-suite only, so on Windows run that task in WSL; where `suprove` is missing, `sby -f <stem>.sby` (all tasks) ends in ERROR for `live`, so name the other tasks (`bmc`, `cover`, `prove_kind`, `prove_pdr`) explicitly. The other tasks ignore the `$live` cell (opt-in tests run `bmc`, `cover` and both proofs on a model with liveness). Run `sby -f <stem>.sby` (all tasks) or `sby -f <stem>.sby <task>` in the output directory (with the oss-cad-suite: yosys, the slang plugin and a solver such as yices).
- Monitor style (the default) checks generic properties with a procedural checker. Each sampling edge after reset sees one trace row: the registers before the edge and root inputs through their copies. Conditions are rendered by the Verilog emitter with the encodings, literal parameters and conversion helpers of the RTL, so fixed-point arithmetic is the RTL's.
- Every generic property kind is monitored, each with `from_step`. A trigger `T` counts on rows at or after `from_step`.
- `when T then P after n` and `when T then P within [a, b]` keep age-indexed pending bits `[d:1]` (`d` = `n` or `b`): bit `k` is a trigger `k` rows ago whose obligation is still open. At each row, a pending obligation inside its window (age `>= a`) is cleared when `P` holds, and the obligation of age `d` fails when `P` does not hold. With `d = 0` there are no pending bits: the trigger row itself is checked. A failure reports its trigger row and the detection row. At the end, the remaining pending bits are the open obligations: with `strict` semantics the earliest fails at the last row; with `weak` semantics the result is `pending` with one `SVA_OPEN <id> <trigger_row>` line per obligation, oldest first.
- `when T then_always P after n` keeps an `armed` flag set by the first trigger and, for `n > 0`, a counter of rows since that trigger that saturates at `n`; from age `n` on, every row where `P` does not hold fails, reported with the first trigger's row. Later triggers add nothing, as in `native`.
- `from_step` and `within` windows use one shared saturating counter `sva_step`, emitted only when needed; it stops one above the largest row compared with. An unbounded `eventually` keeps a `seen` flag (monitor state, also used by the formal liveness check); `eventually within [a, b]` keeps a `seen` flag for rows `from_step + a` .. `from_step + b` and fails at row `from_step + b` when the condition never held in the window. A `cover` keeps a `covered` flag.
- The result recorder is simulation-only (`` `ifndef FORMAL ``): it latches the first failure and its row (64-bit `sva_row`), and the task `sva_report(output bit failed)` prints, in YAML order, one `SVA_RESULT <id> <status> <trigger_row|-> <reported_row|->` line per property and one `SVA_OPEN <id> <trigger_row|end>` line per open obligation. Statuses and rows are those `native` reports on the same trace: at the end, an obligation still open fails at the last row with `strict` semantics and is `pending` with `weak` semantics (effective for the `sva` backend). `failed` is set when a property failed. Generated names start with `sva_` and avoid every port and copy name. An RTL signal read by the checker whose name is one the checker declares itself (the task `sva_report`, a literal parameter such as `_VAL_2_0`, a conversion helper `conv_...`) is an error asking to rename it.
- Concurrent style (`--sva-style concurrent`, simulation only, `strict` semantics only): each generic property becomes one `assert property` (`cover property` for `cover`) with `@(posedge <clock>) disable iff (<reset active>)`, for simulators with full SVA support. A saturating row counter `sva_step` gives `active` (row `>= from_step`) and `first` (row 0). Encodings: `always P`: `active |-> P`; `never P`: `active |-> !P`; `eventually P`: `first |-> strong(##[f:$] P)`; `eventually P within [a, b]`: `first |-> strong(##[f+a:f+b] P)`; `when T then P after n` / `within [a, b]`: `active && T |-> strong(##[n:n] P)` / `strong(##[a:b] P)`, and `|-> P` for zero bounds; `when T then_always P after n`: `active && T |-> nexttime[n] always P` (weak: a run that ends first passes, as in `native`); `cover P`: `cover property (active && P)`. Strong operators make obligations still open at the end of the run fail, as `native` does with `strict` semantics. There is no result recorder and no `sva_report`: a failing assertion reports `SVA_FAIL <id> row <row>` (the evaluated row, `$sampled` of `sva_row`) from its action block, a cover `SVA_COVER <id> row <row>`, and the testbench ends with `$finish`.
- Tool support of the concurrent style, checked locally (opt-in tests); the full forms are meant for simulators with complete SVA support, and the monitor style (compared with `native`) works everywhere else:

  | Tool | `always`, `never`, zero-bound responses | `strong(##[a:b])`, `##[f:$]` (eventually, windows, `after n > 0`) | `nexttime[n] always` (`then_always`) | `cover property` |
  |---|---|---|---|---|
  | slang (yosys-slang, `read_slang --ast-compilation-only`) | parses and elaborates | parses and elaborates | parses and elaborates | parses and elaborates |
  | Verilator 5.047 (`--binary --assert`) | runs, results match `native` | unsupported (build error) | unsupported (build error) | builds, never reports |
  | Icarus Verilog 14 | compile error ("concurrent_assertion_item not supported") | compile error | compile error | compile error |

- Stimulus (`--sva-inputs`): the file is read like `nnc-verify --inputs` (same reader, delimiter and skip-lines; a header without records is zero records). Each value is encoded for its root input port as the RTL encodes constants: `round(value * 2^frac_bits)` for fixed point, `round(value)` for logic. Non-finite values, and values or initial values that do not fit the port (signed or unsigned range of its width, including finite values so large that scaling them overflows), are errors naming the file, line and input; values outside an `environment` range give a warning (once per input). A root input that is not an RTL port (bound to an external output) cannot be driven and is an error.
- `<stem>_inputs.hex` starts with the options comment and a comment naming the inputs in declaration order, then has one line per record with one word per input: the encoded value in two's complement, masked to the port width, zero-padded to `ceil(width/4)` hex digits. It is not written for zero records. `<stem>_inputs_decoded.csv` holds the encoded values decoded back to reals (comma-delimited, a header with the root input names in declaration order); `nnc-verify MODEL.yaml --inputs <stem>_inputs_decoded.csv` checks the same quantized inputs as the RTL.
- The checker module `<module>_sva` and the testbench module `<module>_tb` must not be module names of the RTL closure (for example an imported module named `<root>_sva`); otherwise generation fails and asks to rename that module.
- Testbench `<stem>_tb.sv` (module `<module>_tb`): it instantiates the RTL and the checker side by side and connects the checker by hierarchical names (`dut.<signal>`), not with `bind`. Inputs start at their encoded initial values. The reset is active from time 0, applied at the first rising edge and released at the next falling edge; record `k` (`k = 1..N`) is driven at a falling edge before sampling edge `k - 1`, so sampling edge `j` (`j = 0..N`) sees row `j`. After edge `N`, at the falling edge, it calls `sva_report` (when the checker has generic properties) and ends with `$fatal` if a property failed, `$finish` otherwise. With stimulus it loads `<stem>_inputs.hex` with `$readmemh` from the working directory, or from `+stimulus=<path>`; with zero records or `--sva-steps` it has no stimulus array, no `$readmemh` and no indexing (`--sva-steps N` runs `N` steps). The clock period is 10 time units of a `` `timescale 1ns/1ps``. The testbench's own names (parameters `RECORDS`/`INPUTS`, instances, variables) avoid the RTL port names. To simulate, compile every `.sv` file of the output directory and the copied `sva_sources/` files, for example `iverilog -g2012 -o sim.vvp *.sv sva_sources/*` then `vvp sim.vvp` in that directory.
- Counterexample replay (`--sva-replay WITNESS.yw`, simulation, monitor style with generic properties; otherwise an error): `nnc-gen` generates a self-checking replay, it does not run a simulator. The stimulus comes from a SymbiYosys witness of the generated formal checks: a `bmc` trace (`<stem>_bmc/engine_0/trace.yw`) or a `cover` trace (`trace<N>.yw`); proof counterexamples (k-induction, PDR) are not supported, induction traces are rejected and the timing of PDR traces is not tested. Works for models with or without inputs. Step 0 of the witness is the reset step and must have the reset active, every later step inactive; the input port values of step `k` become record `k`, as encoded words (no rounding), and a witness of `n` steps replays rows `0..n-3`. The testbench, `<stem>_inputs.hex` and `<stem>_inputs_decoded.csv` are written as for `--sva-inputs` (models without inputs: the number of rows), with a comment naming the witness and the expected row. The checker also records the first row each cover was hit, and its task `sva_replay_check(row, reproduced)` tells whether a generic property first failed, or a cover was first hit, on that row (BMC stops at the earliest failure and cover finds the shortest trace, so that is the witness's last row). After the run the replay testbench prints `SVA_REPLAY reproduced on row N` and ends with `$finish`, or ends with `$fatal` and `SVA_REPLAY NOT reproduced ...`: for a replay, success is reproducing the failure, not passing. A witness is matched to the model by its ports only, not authenticated: a witness of other checks with the same ports is accepted and then not reproduced. `nnc-verify MODEL.yaml --inputs <stem>_inputs_decoded.csv` (or `--steps N`) then tells whether the model agrees or diverges (fixed-point arithmetic), which is not a replay failure. The witness is checked before use: a Yosys witness with well-formed signals, the exact number of bits in every step (fragments marked `init_only` count in step 0 only), and only `0`, `1`, `x`, `?` bits. A port may be split into fragments, assembled by their `offset`. Reset bits must be 0 or 1; input bits the solver left unconstrained (`x`, `?`) are replayed as 0. Witness errors (not a Yosys witness, malformed, too short, a missing port, an unknown reset, not starting from the reset) name the file.
- Generation warns when the monitors keep more than 65,536 bits of state: the step counter, `seen`, `covered` and `armed` flags, `then_always` age counters and the pending vectors of `after`/`within` properties (`n` or `b` bits each). Input copies and the simulation-only result diagnostics are not counted. The warning gives the count and suggests lowering the bounds or `--sva-max-bound`.

## FPGA Examples
- The `examples/fpga/ledwalk.yaml` Tang Nano 20K example uses active-low LED semantics (`0` drives LED ON) and implements a walking-zero pattern on `leds[5:0]`.
