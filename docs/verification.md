# TENNCell Verification Specification (v1)

> **Status: partly implemented.** This document describes the intended
> verification layer. Each part becomes a contract only when its implementation
> slice lands and the corresponding rules are added to `rules.md`.
>
> Implemented so far:
>
> - parsing and validation of the `verification` section, including generic
>   property kinds, bounds, and conditions bound to the model (sections 4.1-4.6);
> - `${name}` placeholders in raw code, resolved against the model;
> - MC2 generation with `nnc-gen -t mc2` (section 7.3), for raw entries and
>   generic properties;
> - the `native` checker (section 6.6) and its command `nnc-verify`, which
>   simulates the model or reads a recorded trace.
>
> Not implemented yet: `sva`, and trace export of internal variables.

## At a glance

This section is a non-normative summary. Sections 1 to 9 are the specification.

- **Purpose:** an optional top-level `verification` section describes **what** to
  verify, never **how** to run it. Steps, stimulus files, trace files, seeds and
  tool invocation are out of scope.
- **Shape:** the section has four keys, `environment`, `trace_semantics`,
  `properties` and `backends`. A full example is in section 2.
- **Backends:**

  | Backend | Kind of check | Output |
  |---|---|---|
  | `native` | built-in checker; also the semantic reference for testing the others | results |
  | `mc2` | trace-based | PLTLc query files (one query per line) |
  | `sva` | simulation and/or formal | SystemVerilog assertion files |

  `prism`, `spin`, `english` and `custom` are reserved. External backends only
  generate files in v1; they don't run tools.
- **Generic properties:** flat kinds written with bare TENNCell expressions:

  | Kind | Keys |
  |---|---|
  | `always` | `always: P` |
  | `never` | `never: P` |
  | `eventually` | `eventually: P`, optionally with `within: [a, b]` |
  | response | `when: T` + `then: P` + one of `after: n` or `within: [a, b]` |
  | persistence | `when: T` + `then_always: P`, optionally with `after: n` |
  | `cover` | `cover: P` |

  Nesting is not supported in v1.
- **Raw code:** `backends.<name>.raw` holds code in the backend's own language.
  `${name}` placeholders are checked against the model; all other text passes
  through unchanged.
- **End of trace:** with `trace_semantics: strict`, obligations still open when
  the trace ends `fail`; with `weak`, they are `pending`.

## 1. Purpose and scope

TENNCell verification lets a user write properties once, against the TENNCell
model, and check them with several verification backends:

- **trace-based** checking: properties are evaluated over a finite simulation
  trace (`native`, `mc2`);
- **model-based** checking: properties are attached to a generated model and
  checked by an external tool (`sva` in formal mode; `prism` and `spin` later).

`sva` is used in both ways. In simulation mode it checks the trace produced by an
RTL simulation, and in formal mode it is checked against the RTL model.

The `verification` section describes **what** is verified and the semantic
assumptions that verification depends on. It does not describe **how** a check is
executed.

### Out of scope for v1

- Execution configuration: number of steps, stimulus files, existing trace files,
  run counts, seeds and tool invocation. These belong to the CLI or to a later
  `run` section.
- Running external tools. External backends generate files only.
- Probabilities and input distributions (the names are reserved).
- Nested temporal formulas or full LTL (see the future path in section 4.7).
- Formal English properties, PRISM, SPIN and a `custom` backend (the names are
  reserved).
- `verification` sections in imported modules.

## 2. Example

The example uses names from `examples/fsm/fsm_counter.yaml`.

```yaml
verification:
  environment:                      # per-input assumptions
    start: { range: [0, 1] }
  trace_semantics: strict           # strict | weak

  properties:
    - id: bounded
      description: Counter never exceeds its maximum
      always: counter <= MAX_COUNT

    - id: done_follows_start
      description: After start is raised, done is set within 1 to 10 steps
      when: start > 0
      then: done == 1
      within: [1, 10]
      targets: [native, sva]

    - id: stays_done
      description: Once the controller is in DONE, done stays set
      when: ctrl_state == ctrl.DONE
      then_always: done == 1
      after: 0

    - id: reaches_done
      eventually: ctrl_state == ctrl.DONE

  backends:
    mc2:
      raw:
        - id: raw_reach
          code: "P=?[ F([${done}] = 1) ]"   # one MC2 query per entry
    sva:
      mode: simulation              # simulation | formal | both
      raw:
        - id: raw_resp
          code: |
            assert property (@(posedge clk) ${start} |-> ##[1:10] ${done});
```

## 3. Section schema

`verification` is an optional top-level mapping with these keys:

| Key | Type | Required | Meaning |
|---|---|---|---|
| `environment` | mapping | no | Assumptions about root input variables (section 3.2) |
| `trace_semantics` | `strict` \| `weak` | no, default `strict` | End-of-trace handling (section 6) |
| `properties` | list | no | Generic, backend-neutral properties (section 4) |
| `backends` | mapping | no | Backend-specific options and raw code (section 5) |

Unknown keys are errors.

### 3.1 Scope

- Only the root module's `verification` section is used in v1. If an imported
  module has a `verification` section, it is ignored.
- Properties in the root module may reference imported inputs and outputs, such
  as `sensor0.level`.
- `NncSystem.from_yaml()` ignores the `verification` section, in the same way it
  ignores `verilog` and `webots`.
- Repeat sugar (`${i}`) is not applied inside `verification`.

### 3.2 `environment`

- Keys are TENNCell **input variables of the root module** only. Any other name
  is an error.
- Each value is a mapping. v1 defines one field:
  - `range: [lo, hi]`: numeric bounds with `lo <= hi`, both inclusive.
- `distribution` is reserved for future probabilistic backends and is rejected in
  v1.
- `environment` is global only. Backend sections cannot override it in v1.
- How each backend uses `environment` is part of its contract. For example,
  formal SVA turns ranges into input assumptions.

### 3.3 Backend names

| Name | v1 status |
|---|---|
| `native` | accepted |
| `mc2` | accepted |
| `sva` | accepted |
| `prism`, `spin`, `english`, `custom` | reserved; rejected until implemented |
| any other name | rejected |

### 3.4 Identifiers

- Every generic property and every raw entry has an `id`.
- IDs must be unique **within each backend's emitted set**:
  - a generic property ID must not collide with a raw entry ID of any backend
    the property targets;
  - raw entry IDs may repeat across different backends.
- IDs should be valid identifiers (`[A-Za-z_][A-Za-z0-9_]*`), because backends
  may use them as labels in generated code.

### 3.5 Includes

- `verification` may appear in included fragments (`module.include`).
- The intended merge behavior is:
  - the `properties` list and each backend's `raw` list are concatenated in
    include order;
  - mappings merge recursively;
  - conflicting scalars are errors.

  This is the same behavior as other include-merged sections.
- Include merging and backend overrides are separate mechanisms:
  - include merging combines YAML **files** before parsing, so two fragments that
    set the same scalar (for example both setting `backends.sva.mode`) to
    different values is an error;
  - a backend override is a **semantic** rule applied after merging, so
    `backends.<name>.trace_semantics` replacing the global `trace_semantics` is
    allowed (section 6.4).

## 4. Generic properties

**Implemented** (parsing and binding; checked by `native`, translated by `mc2`).
A user guide with worked examples is `docs/generic_properties.md`.

Generic properties have TENNCell semantics and are translated by each backend
that supports them.

### 4.1 Expressions

- Conditions (`P`, `T`) use TENNCell guard/expression syntax with **bare names**,
  as in `rules`. They are validated against TENNCell semantics: every name must
  resolve.
- Allowed references are:
  - local variables;
  - constants;
  - aliases;
  - imported inputs and outputs (`sensor0.level`);
  - dotted FSM state constants (`ctrl.DONE`).

  Dotted FSM state constants are explicitly valid in verification expressions,
  with the same meaning as in `rules`.
- `${...}` placeholders are not used in generic properties. They belong to raw
  backend code only (section 5).

### 4.2 Kinds

v1 properties are **flat named kinds**, not full LTL. Each entry has exactly one
kind. The kind is determined by the exact set of kind keys present. The table
lists every valid combination. In the table:

- `t` is a step at which the trigger `T` holds;
- `f` is `from_step`.

| Keys | Meaning |
|---|---|
| `always: P` | `P` holds at every step `>= f` |
| `never: P` | `P` holds at no step `>= f` |
| `eventually: P` | `P` holds at some step `>= f`. Unbounded; see note below |
| `eventually: P`, `within: [a, b]` | `P` holds at some step in `f+a .. f+b` |
| `when: T`, `then: P`, `after: n` | `T` at `t` implies `P` at `t+n` |
| `when: T`, `then: P`, `within: [a, b]` | `T` at `t` implies `P` at some step in `t+a .. t+b` |
| `when: T`, `then_always: P` [, `after: n`] | `T` at `t` implies `P` at every step `>= t+n`; `after` defaults to `0` |
| `cover: P` | `P` is reached at some step `>= f`. Reported, not asserted |

Notes:

- Unbounded `eventually` is liveness-like. Some backends, or some backend modes,
  may not support it (see section 7).
- `when: T` + `then: P` requires exactly one of `after` or `within`.
- Without a trigger, the window of `eventually` + `within` is relative to
  `from_step`.

Any other combination of kind keys is an error. Examples:

- `always` + `within`;
- `when` without `then` or `then_always`;
- `then` together with `then_always`;
- two kinds in one entry, such as `always` + `never`;
- `then_always` + `within`.

### 4.3 Shared fields

| Field | Type | Default | Meaning |
|---|---|---|---|
| `id` | identifier | required | Property identity (section 3.4) |
| `description` | string | none | Human-readable text. It has no semantics |
| `targets` | list of backend names | all accepted backends that support the kind | Backends the property is emitted to |
| `from_step` | non-negative integer | `0` | First step at which the property is evaluated |

`probability` is a reserved per-property field and is rejected in v1.

If a property lists a backend in `targets` and that backend does not support the
property's kind, it is an error. A property that names no `targets` is not
emitted by backends that don't support its kind, and each such backend reports
it as skipped (unsupported kind).

### 4.4 Bounds

- `within: [a, b]` takes non-negative integers with `a <= b`. Both ends are
  inclusive.
- `after: n` takes a non-negative integer.
- `from_step` takes a non-negative integer.

### 4.5 Triggers

- In `when` kinds, **every** step `t >= from_step` at which `T` holds opens its
  own, independent obligation. Overlapping obligations are all checked.
- Steps before `from_step` never trigger.

### 4.6 No nesting

Properties cannot be nested. This is invalid in v1:

```yaml
- id: invalid_nested
  always:
    always: done == 1
```

To express the same intent, use one of the flat kinds:

```yaml
- id: stays_done
  when: ctrl_state == ctrl.DONE
  then_always: done == 1
  after: 0
```

### 4.7 Future evolution path (non-normative)

> **Non-normative: `formula:` is not accepted in v1.**
>
> The v1 kinds are chosen so that each one lowers directly to an explicit
> temporal formula. A future version may add a `formula:` key that allows
> nesting. The v1 kinds would then become sugar for it, so v1 files stay valid.
> Sketch only:
>
> ```yaml
> formula:
>   always:
>     implies:
>       if: start > 0
>       then:
>         eventually: { within: [1, 10], expr: done == 1 }
> ```

## 5. Raw backend code

Raw code lets users write properties directly in a backend's own language, while
TENNCell still validates every reference to the model.

### 5.1 Shape

```yaml
backends:
  <backend>:
    raw:
      - id: <identifier>
        description: <optional text>
        code: |
          <backend-specific text with ${name} placeholders>
```

### 5.2 Placeholders

- `${name}` marks a reference to a TENNCell name. `name` may be:
  - a local variable;
  - a constant;
  - an alias, rendered as its target (TENNCell aliases are reference-only, so
    no expression translation is needed);
  - an FSM state constant (`${ctrl.DONE}`);
  - an imported input or output (`${sensor0.level}`).
- An unknown name is an error.
- A name that could refer to more than one thing is also an error. There is no
  priority-based resolution.
- Errors report the YAML file and line, like other loader errors.
- `$${` escapes a literal `${` in the emitted text.
- Text outside placeholders is passed through **unvalidated**. TENNCell does not
  parse MC2, SVA or any other backend language.
- Each backend defines how a placeholder is rendered: for example, as a trace
  column name for `mc2`, or as an RTL signal name or encoded constant for `sva`.

### 5.3 Quoting

- Raw code should be written as a YAML block scalar (`code: |`). Inside a block
  scalar, `#` is ordinary text. In an unquoted plain scalar, a `#` preceded by
  whitespace starts a YAML comment, so an SVA delay such as `... |-> ##[1:10] ...`
  would be cut off without any error. Quoted strings are also safe, but block
  scalars avoid escaping.
- The default `|` style ends the text with exactly one newline. Renderers strip
  that one final newline and keep the rest of the raw text exactly as written.

## 6. Trace semantics

**Implemented** in `native` (section 6.6) and in the `mc2` translation
(section 7.3.1).

These rules apply to every check over a finite trace: `native`, `mc2`, and `sva`
in simulation mode.

### 6.1 Steps

- Step `0` is the initial state, before any step has executed.
- After-step rows start at step `1`. This is the existing TENNCell CSV
  convention.

### 6.2 Results

- Asserted properties report `pass`, `fail` or `pending`. A `fail` also reports
  the first step at which the property failed.
- `cover` properties report `covered` or `not_covered`.

### 6.3 End of trace

Obligations fall into two groups:

- **Hold throughout:** `always`, `never`, `then_always`. They pass if no
  violation appears before the trace ends.
- **Must happen:** `eventually`, `within` windows, and `then` with `after`. An
  obligation can still be open when the trace ends: its window or target step
  lies beyond the last step, or `eventually` has not been met yet. Such an
  obligation is resolved by `trace_semantics`:
  - `strict` (default): it **fails**. This is finite-trace LTL. It matches MC2
    v2.0beta2, confirmed against the tool: an unmet `F` gives `0.0`, and `X` at
    the last step is false.
  - `weak`: it is **pending**.

| Kind | Situation at trace end | `strict` | `weak` |
|---|---|---|---|
| `always`, `never` | no violation seen | `pass` | `pass` |
| `when` / `then_always` | no violation seen (trigger obligations still active) | `pass` | `pass` |
| `eventually` (unbounded) | `P` not yet seen | `fail` | `pending` |
| `eventually` + `within` | window ended inside the trace and `P` not seen | `fail` | `fail` |
| `eventually` + `within` | window extends past the trace and `P` not seen yet | `fail` | `pending` |
| `when` / `then` / `within` | some window ended inside the trace without `P` | `fail` | `fail` |
| `when` / `then` / `within` | some window extends past the trace and `P` not seen yet | `fail` | `pending` |
| `when` / `then` / `after` | some target step `t+n` lies past the trace | `fail` | `pending` |
| `cover` | `P` not seen | `not_covered` | `not_covered` |

- Any violation seen inside the trace is `fail` under both settings.
- If several obligations of one property have different outcomes, the property
  result is the worst one, in the order `fail` > `pending` > `pass`.

### 6.4 Overriding `trace_semantics`

- `trace_semantics` is a global default. A backend section may override it by
  replacing the value: `backends.<name>.trace_semantics`.
- A backend that cannot honor a setting exactly must either reject it or document
  its reinterpretation in its generated output.

### 6.5 Missing trace data

If a property references a variable that is absent from a supplied trace, this
is an **error**, never a silent `pass`.

### 6.6 Rows, edge cases, and reporting (native, implemented)

- **Time is row position.** `after`, `within`, and `from_step` count trace
  rows, exactly as MC2's `X` counts rows. Step or time labels (the first trace
  column, if any) are only used for reporting. Labels must be finite and
  strictly increasing.
- **Empty range** (`from_step` past the end of the trace, that is, at least the
  number of rows): `always`, `never`, and
  trigger kinds pass; `eventually` and `eventually` + `within` fail under
  `strict` and are `pending` under `weak`; `cover` is `not_covered`.
- **`then_always` is "hold throughout" under both semantics.** Rows past the
  end are never checked, so a trigger too close to the end for `t+n` to exist
  passes even under `strict`.
- **What a failure reports.** The trigger row (for trigger kinds) and the row
  where the failure became known, each with its label:

  | Kind | Reported row |
  |---|---|
  | `always`, `never`, `then_always` | first violating row |
  | `when` / `then` / `after: n` | `t+n` |
  | `when` / `then` / `within: [a, b]` | `t+b` |
  | `eventually` + `within: [a, b]` | `from_step+b` |
  | strict end-of-trace failure | last row |

  When several obligations fail, the one with the earliest reported row is
  reported; ties go to the earliest trigger. Pending results list every open
  obligation's trigger row and label.
- **Errors, not failures.** A missing column, a non-finite value in a column a
  checked property uses, or an error while evaluating a condition (for example
  `sqrt` of a negative value) is an operational error naming the property, the
  condition, the row, and the label.

## 7. Backend contracts

### 7.1 Common rules

- Backend sections are optional. A section is needed only for backend options, a
  `trace_semantics` override, or raw code.
- Keys allowed in a backend section are `trace_semantics`, `raw`, and the
  backend-specific options listed below. Any other key is an error.
- External backends (`mc2`, `sva`) **generate files only** in v1. They do not
  execute tools.
- Each backend declares which generic kinds it supports.

### 7.2 `native`

- **Implemented:** `nnc-verify` (see `rules.md`, section "nnc-verify").
- The built-in checker. It runs in-process and needs no external tool.
- It either simulates the model through `NncSystem` or checks a supplied trace.
  How the run or trace is selected is an execution concern and is out of scope
  here.
- It supports every v1 kind and follows section 6 exactly.
- It is also the **semantic reference** used to test the other backends.
- It checks the abstract TENNCell model, which uses the Python simulator's float
  arithmetic. The generated RTL uses fixed-point (`verilog.real_encoding`), so
  `sva` results may legitimately differ from `native` near thresholds.
  Cross-backend tests must account for this.
- `native` does not accept raw code in v1.
- Options: none in v1.

### 7.3 `mc2`

- Trace-based file generator for the MC2 Monte Carlo model checker
  (PLTLc, Donaldson and Gilbert).
- **Implemented:** `nnc-gen -t mc2 model.yaml` emits, for raw entries and
  generic properties (section 7.3.1):
  - `<stem>.mc2.pltl`: the PLTLc queries, one per line: raw entries first, then
    generic properties, each in YAML order;
  - `<stem>.mc2.columns`: the trace columns those queries need, in first-use
    order;
  - `<stem>.mc2.ids`: the entry IDs, in query order.
- It fails if nothing is emitted (no `mc2.raw` entries and no generic property
  for MC2).
- **Trace workflow (implemented):** traces come from one of two sources.
  - **`nnc-sim`** writes only root output variables, so every variable a query
    uses must be declared as a root output; root inputs and imported
    inputs/outputs cannot be traced. MC2 needs a leading time column, which
    `nnc-sim --csv-include-step` adds in IO mode (compute-mode CSV always starts
    with `step`):
    `nnc-sim model.yaml in.csv trace.txt --csv-include-step --csv-include-initial --csv-delimiter " "`,
    then `java -jar MC2v2.0beta2.jar stoch trace.txt model.mc2.pltl`.
  - **The Webots controller's CSV log** (`webots.csv`) records any listed
    variable, including inputs. For MC2 it needs `include_step: true` (so the
    first column is `_step`) and `delimiter: " "` (or `";"` with `-snoopy`).
  - `nnc-gen -t mc2` warns about columns that neither source records. With a
    `webots.csv` section, it also warns when `include_step` is false or the
    delimiter is not a space, tab, or `;`.
- **Query file format** (MC2 user manual, checked against MC2 v2.0beta2):
  - plain text, **one query per line**; blank lines are ignored, and CRLF or LF
    line endings both work;
  - each query is a complete formula with its probability operator, for
    example `P=?[ ... ]` (probability) or `P>=1[ ... ]` (bounded check, which
    prints `true` or `false`);
  - MC2 has no comment syntax, so the query file contains queries only.
    IDs and descriptions are kept in separate files;
  - MC2 removes all whitespace before parsing.
- **PLTLc operators accepted by MC2 v2.0beta2** (from its parser tokens and
  tested):
  - temporal: `X`, `F`, `G`, `U`, `R`, and the `{...}` start condition;
  - boolean: `^` (and), uppercase `V` (or), `->` or `=>` (implies), and the
    NOT sign U+00AC (negation). `!`, `&`, `|`, `~`, `NOT`, and lowercase `v`
    are rejected; `!` is only valid inside `!=`;
  - comparisons `=`, `!=`, `<`, `<=`, `>`, `>=`; arithmetic `+`, `-`, `*`, `/`;
    `true`, `false`, `time`, and decimal or negative numbers;
  - query files are read in the JVM default encoding. `nnc-gen` writes UTF-8,
    which Java 18+ reads by default; with older Java, run
    `java -Dfile.encoding=UTF-8 -jar ...` so the NOT sign is decoded.
- **Semantics to know when writing MC2 queries** (tested with MC2 v2.0beta2;
  the generic-properties translation must follow them). Below, `<not>` stands
  for the NOT sign U+00AC, which is what the query file must contain:
  - **`->` with `X` is broken.** `a -> b` evaluates to false whenever `b`
    contains `X`, even when `a` is false: `P=?[ [x] = 5 -> X(true) ]` gives
    `0.0` on a trace where `x` is never 5. Write `<not>(a) V b` instead. `->` works correctly with `F`, `G`, and plain
    comparisons.
  - **The end of the trace is strict.** `X` past the last step is false, and
    an unmet `F` is false, matching `trace_semantics: strict`. The weak form of
    "after n steps" adds `V <not>X(...X(true)...)` with n `X`s, so a trigger in the
    last n steps does not count as a failure.
  - **There is no bounded `F`.** "Within `[a, b]` steps" must be written as
    `X^a(p) V ... V X^b(p)`, nested `X`s. This is practical only for small
    bounds.
  - **"Always" needs `G`.** `F(a ^ X(b))` only asks whether the pattern happened
    at least once. A rule "whenever `a`, then `b` next" is
    `G(<not>(a) V X(b))`.
- **Raw code rules:**
  - each raw entry is exactly one query. Code that still spans several lines
    after the final-newline strip (section 5.3) is an error. Long queries can use
    YAML folded style (`code: >-`), which joins lines with spaces;
  - MC2 has no `#` delay operator, so a quoted one-line string is fine.
- **Placeholders** render as the **bare trace column name**. The user writes the
  MC2 brackets, which also allows the MC2 functions:
  - `[${done}]` gives the value of `done`;
  - `d[${done}]` gives its derivative;
  - `max([${done}])` gives its maximum over the trace.
- **Column names:**
  - a local variable uses its name;
  - an imported input or output `alias.port` uses `alias__port`, because MC2
    does not document dots in names;
  - an alias uses its target's column;
  - constants and FSM states render as numeric literals and need no column.
- **Trace format** (tested with MC2 v2.0beta2, `stoch` mode):
  - a header line, then one row per time point;
  - the **first column is always time**, whatever its name (`step`, `Time`,
    and `time` all work). Without a time column the first variable is consumed
    as time and queries on it fail with "Did not find species";
  - whitespace-separated by default; `-snoopy` selects `;`-separated CSV;
  - several runs in one file (for probabilities) are supported in the
    whitespace format: runs are separated by a blank line and each run repeats
    the header. The `-snoopy` parser rejected every multi-run layout tried;
  - `det` mode expects the BioNessie format and does not read these traces, so
    a single deterministic TENNCell run is checked with `stoch`.
- Options: none in v1. Run counts and seeds are execution configuration.

#### 7.3.1 Generic properties (implemented)

- **Selection.** Properties without `targets`, or listing `mc2`, are translated.
  MC2 supports every kind but **no function calls**: a property with a call is
  an error when it lists `mc2` in `targets`, and is otherwise skipped with a
  warning. Properties targeting only other backends are omitted silently.
- **IDs.** An emitted property ID must differ from every `mc2.raw` ID. The check
  runs after filtering, so a native-only property may reuse a raw MC2 ID.
- **Notation.** `X^k(p)` is k nested `X` (`X^0(p) = p`); `W_k = ¬X^k(true)`,
  "the trace ends within k rows"; `C(p)` is the translated condition;
  `R(p, w) = p V X(p V X(... X(p)))` with `w` nested `X`, which is
  `X^0(p) V ... V X^w(p)` in linear size.
- **Bodies.** Every query is `P=?[ <wrapped body> ]`:

  | Kind | Strict body | Weak body | `from_step f > 0` wrapper |
  |---|---|---|---|
  | `always P` | `G(C(P))` | same | `W_f V X^f(body)` |
  | `never P` | `G(¬(C(P)))` | same | `W_f V X^f(body)` |
  | `eventually P` | `F(C(P))` | same: pending cannot be expressed, so MC2 checks strictly (warning) | `X^f(body)` |
  | `eventually P within [a,b]` | `X^a(R(C(P), b-a))` | strict body `V W_b` (none for `b = 0`) | strict: `X^f(body)`; weak: `W_f V X^f(weak body)` |
  | `when T then P after n` | `G(¬(C(T)) V X^n(C(P)))` | adds `V W_n` inside `G` (none for `n = 0`) | `W_f V X^f(body)` |
  | `when T then P within [a,b]` | `G(¬(C(T)) V X^a(R(C(P), b-a)))` | adds `V W_b` inside `G` (none for `b = 0`) | `W_f V X^f(body)` |
  | `when T then_always P after n` | `G(¬(C(T)) V W_n V X^n(G(C(P))))` (no `W_0`) | same | `W_f V X^f(body)` |
  | `cover P` | `F(C(P))` | same | `X^f(body)`; covered when the result is > 0 |

- The wrappers make `f >= L` agree with the native table: safety and trigger
  kinds give 1; strict `eventually`, strict bounded `eventually`, and `cover`
  give 0; weak bounded `eventually` gives 1.
- **Weak approximation.** MC2 has no `pending`. With `weak`, bounded
  `eventually` and response properties give 1 when an obligation is still open
  at the end, and unbounded `eventually` gives 0; `nnc-gen` warns about both.
  With a zero bound (`after: 0`, `within: [0, 0]`, and for bounded `eventually`
  also `from_step: 0`), nothing can stay open, the weak query is exact, and
  there is no warning.
- **Conditions.** Variables render as `[name]`, imported IO as `[alias__port]`,
  aliases as their target, constants and FSM states as numbers (negative ones
  as `(-n)`). `&&` becomes `^`, `||` becomes `V`, `!x` becomes `¬(x)`, `==`
  becomes `=`, unary minus becomes `-(x)`; `!=`, `<`, `<=`, `>`, `>=`, `+`, `-`,
  `*`, `/`, `true`, and `false` are kept. Every binary operation is
  parenthesized. `->` is never emitted, because of the MC2 bug with `X`.
- **Agreement with `native`** is tested on recorded traces with the MC2 jar
  (opt-in): `pass`/`covered` give 1, `fail`/`not_covered` give 0, and weak
  `pending` gives 1, except unbounded `eventually`, which gives 0.

### 7.4 `sva`

- SystemVerilog assertion file generator.
- **Model:** the RTL generated by the TENNCell Verilog backend.
- **Option:** `mode: simulation | formal | both` (default `simulation`). It
  selects which files are generated.
- **Step mapping:**
  - step `0` is the state right after reset is released;
  - one TENNCell step is one cycle of `verilog.clock`;
  - assertions are disabled while `verilog.reset` is active.
- **Placeholders** render as the emitted RTL signal names: internal state,
  ports (including `rename`) and import wires. Constants render in the module's
  `verilog.real_encoding`.
- **End-of-trace semantics:** weak or strong SVA encodings are chosen to follow
  `trace_semantics`. If an exact mapping is not possible for a property, the
  backend must either reject it or document the bounded or weak reinterpretation
  in the generated output.
- **Formal mode:**
  - `environment.<input>.range` becomes input assumptions;
  - unbounded kinds may be bounded or unsupported, and this must be documented
    in the generated output.
- **Target toolchain:** open-source tools, namely Verilator for simulation and
  SymbiYosys/Yosys for formal checking. Generic properties must stay within what
  these tools accept. Raw code may use anything the user's tool accepts.

### 7.5 Reserved backends

- `prism`, `spin`: future model-based backends. They will need a finite
  encoding of TENNCell values, reusing `verilog.real_encoding` or something
  similar, and they will need `environment` ranges.
- `english`: a future formal English property syntax that lowers to the generic
  kinds.
- `custom`: a future escape hatch for user-defined backends.

## 8. Implementation notes (non-binding)

These notes guide the implementation slices. They are not part of the contract.

- The section parser will probably be registered through
  `parse_registered_sections` (`src/nnc/inputs/yaml/sections.py`), like
  `verilog` and `webots`.
- The current loader ignores unknown top-level sections. All validation rules in
  this spec (unknown keys, backend names, property kinds, placeholders) must
  therefore be enforced by the verification section parser, not by
  `NncSystem.from_yaml()`. A YAML file with an invalid `verification` section
  will still load and simulate normally; errors appear only when a verification
  path parses the section.
- Include merging: `_LIST_MERGE_PATHS` (`src/nnc/inputs/yaml/includes.py`)
  currently holds concrete paths only. Concatenating `backends.<name>.raw` needs
  either wildcard support or one entry per known backend.
- Placeholder and name validation can build on:
  - the system's variables, constants and aliases;
  - the FSM `__` constant form;
  - imported input/output validation (`NncSystem._validate_reference`).
- MC2 will probably need a simulator option that dumps selected internal
  variables into the trace. Today the simulator writes output variables only.
  `NncSystem.get_variables()` already exposes the internal state.
- SVA will probably need:
  - multi-file output;
  - a checker module plus a `bind` file;
  - a simulation testbench;
  - a SymbiYosys `.sby` file;
  - fixed-point constant encoding via `encode_float`
    (`src/nnc/transformers/verilog/generation/literals.py`).

Suggested implementation order:

1. Section parser and validation.
2. The `native` backend.
3. `mc2`.
4. `sva` in simulation mode.
5. `sva` in formal mode.

## 9. Open items

- Exact CLI commands, flags and output filenames.
- Tracing root inputs and imported inputs/outputs for MC2 (they are not `nnc-sim` output columns).
- Probability syntax, including `environment.<input>.distribution`.
- Constant encoding for variables with non-default `verilog.types` encodings.
- Verification sections in imported modules.
- The formal English grammar.
- The behavior of the `custom` backend.
- An RTL-faithful `native` mode, covering fixed-point and other RTL effects.
- Execution configuration (steps, stimulus, trace file, MC2 run count and seed):
  CLI options or a later `run` section.
