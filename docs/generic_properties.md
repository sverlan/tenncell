# Generic Verification Properties: Syntax and Semantics

This guide explains how to write **generic verification properties** in a
TENNCell model, and what each property means exactly. It is a user guide. The
normative specification is `docs/verification.md` (sections 4, 6 and 7), and
the implemented rules are summarized in `rules.md`.

The examples below use the `native` checker (`nnc-verify`), the MC2 translator
(`nnc-gen -t mc2`) and the SVA backend (`nnc-gen -t sva`).

## Contents

1. [Overview](#1-overview)
2. [Where properties live](#2-where-properties-live)
3. [Property entries](#3-property-entries)
4. [Conditions](#4-conditions)
5. [The time model: rows, steps and labels](#5-the-time-model-rows-steps-and-labels)
6. [The property kinds](#6-the-property-kinds)
7. [End of trace: `strict` and `weak`](#7-end-of-trace-strict-and-weak)
8. [Results and reporting](#8-results-and-reporting)
9. [Targets and backends](#9-targets-and-backends)
10. [Errors that are not failures](#10-errors-that-are-not-failures)
11. [A complete example](#11-a-complete-example)
12. [Patterns and limitations](#12-patterns-and-limitations)
13. [Quick reference](#13-quick-reference)

---

## 1. Overview

A generic property states something that must hold (or, for `cover`, that
should be reached) along a run of the model: a sequence of rows, one per step.
The native and MC2 backends check finite traces; SVA simulation does the same,
while SVA formal proofs range over generated RTL runs and its `live` task uses
infinite-run semantics. Properties are written once, in TENNCell's own
expression syntax, and can then be

- **checked** directly by the built-in `native` checker, with `nnc-verify`,
  on a simulated run or on a recorded trace;
- **translated** to MC2 queries (`nnc-gen -t mc2`) or checked against the
  generated RTL by simulation or formal tools (`nnc-gen -t sva`).

There are eight kinds, each a fixed temporal pattern:

| Kind | Written as | Informal meaning |
|---|---|---|
| `always` | `always: P` | `P` holds on every row |
| `never` | `never: P` | `P` holds on no row |
| `eventually` | `eventually: P` | `P` holds on some row |
| `eventually_within` | `eventually: P` + `within: [a, b]` | `P` holds on some row in a window |
| `response_after` | `when: T` + `then: P` + `after: n` | every `T` is followed by `P` exactly `n` rows later |
| `response_within` | `when: T` + `then: P` + `within: [a, b]` | every `T` is followed by `P` within a window |
| `persistence` | `when: T` + `then_always: P` [+ `after: n`] | after every `T` (and `n` rows), `P` holds until the end |
| `cover` | `cover: P` | `P` is reached at least once (observed, not asserted) |

Properties are **flat**: a kind cannot contain another kind. Section 12 shows
how to express common intents with the flat kinds.

## 2. Where properties live

Properties are listed under `verification.properties` in the **root** model
file. The `verification` section of an imported module is ignored.

```yaml
verification:
  trace_semantics: strict        # optional: strict (default) or weak
  properties:
    - id: level_bounded
      description: The level never exceeds its limit
      always: level <= LIMIT
    - id: request_served
      when: req > 0
      then: ack == 1
      within: [0, 6]
```

The same section can also hold `environment` and `backends` (backend options
and raw backend code); see `docs/verification.md`.

`properties` may also come from included fragments (`module.include`); the
lists are concatenated in include order.

## 3. Property entries

### 3.1 Fields

Each entry is a mapping with these keys:

| Key | Required | Value | Meaning |
|---|---|---|---|
| `id` | yes | identifier `[A-Za-z_][A-Za-z0-9_]*` | Name used in results and generated files. Unique among the properties |
| `description` | no | string | Free text; no semantics |
| kind keys | yes | see 3.2 | Select the kind and give its conditions and bounds |
| `from_step` | no | integer `>= 0`, default `0` | First row at which the property is evaluated (section 5.3) |
| `targets` | no | list of backend names | Backends the property is meant for (section 9). Default: every backend that supports it |

Any other key is an error. `probability` is reserved for a future version and
is rejected.

### 3.2 Kind keys

The kind is determined by the **exact set** of kind keys present
(`always`, `never`, `eventually`, `within`, `when`, `then`, `then_always`,
`after`, `cover`):

| Keys present | Kind |
|---|---|
| `always` | `always` |
| `never` | `never` |
| `eventually` | `eventually` |
| `eventually`, `within` | `eventually_within` |
| `when`, `then`, `after` | `response_after` |
| `when`, `then`, `within` | `response_within` |
| `when`, `then_always` | `persistence` (with `after: 0`) |
| `when`, `then_always`, `after` | `persistence` |
| `cover` | `cover` |

Every other combination is an error that names the problem, for example:

| Entry | Error |
|---|---|
| `when` + `then` (no bound) | `'when' + 'then' needs exactly one of 'after' or 'within'` |
| `when` + `then` + `after` + `within` | `'after' and 'within' cannot be combined` |
| `then` + `then_always` | `'then' and 'then_always' cannot be combined` |
| `when` alone | `'when' needs 'then' or 'then_always'` |
| `then` without `when` | `'then'/'then_always' needs 'when'` |
| `always` + `never`, `always` + `within`, `then_always` + `within` | `invalid combination of keys ...` |
| no kind key | `defines no property kind ...` |

### 3.3 Bounds

- `after: n`: a non-negative integer.
- `within: [a, b]`: two integers with `0 <= a <= b`. **Both ends are
  inclusive.** `within: [n, n]` is the same as `after: n`, and `[0, 0]` means
  "on the same row".
- `from_step: f`: a non-negative integer.

Booleans are not accepted as numbers (`after: true` is an error).

### 3.4 Errors are located

All errors in a property report the YAML file and line, for example:

```text
model.yaml:12: Verification property 'p': 'when' + 'then' needs exactly one of 'after' or 'within'
```

## 4. Conditions

`P` (the condition) and `T` (the trigger) are TENNCell boolean expressions,
the same syntax as rule guards, with **bare names**.

### 4.1 Grammar

| Construct | Syntax | Notes |
|---|---|---|
| Comparison | `e1 OP e2`, `OP` one of `==` `!=` `<` `<=` `>` `>=` | Every condition is built from comparisons. A bare name (`done`) is **not** a condition; write `done == 1`. Comparisons do not chain (`a < b < c` is an error) |
| And | `c1 && c2` | Binds tighter than `\|\|` |
| Or | `c1 \|\| c2` | |
| Not | `!c` | Applies to one comparison, a boolean literal (`!true`), or a parenthesized condition: `!x > 0` means `!(x > 0)`. `!!c` is an error |
| Grouping | `( c )` | |
| Constants | `true`, `false` | Case-insensitive. A YAML boolean (`always: true`) is accepted too |
| Arithmetic | `+` `-` `*` `/`, unary `-`, parentheses | Usual precedence, left-associative |
| Numbers | `3`, `2.5`, `1e-3` | |
| Function calls | `abs(x)`, `max(a, b, c)`, `pi()` | Section 4.3 |

Precedence example: `!(err == 1) && level >= 0 || mode == ctrl.DONE` means
`((!(err == 1)) && (level >= 0)) || (mode == ctrl.DONE)`.

### 4.2 Names

Every name must resolve against the model. An unknown name is an error, not a
missing column.

| Name | Example | Meaning |
|---|---|---|
| Local variable | `level` | Any variable of the root model: inputs, outputs and **internal** variables |
| Constant | `LIMIT` | Replaced by its value |
| FSM state | `ctrl.DONE` | Replaced by the state's number (`ctrl` is the FSM name) |
| Alias | `finished` | Replaced by its target |
| Imported input/output | `sensor0.level` | Port of an imported module (`alias.port`). Internal variables of imported modules are not accessible |

A dotted name that could be both an FSM state and an imported port is an error
(ambiguous). `${...}` placeholders belong to raw backend code only; they are not
used in generic properties.

### 4.3 Functions

Only **unmodified built-in, deterministic** functions are allowed:

`abs`, `acos`, `asin`, `atan`, `atan2`, `ceil`, `cos`, `cosh`, `degrees`, `e`,
`exp`, `floor`, `hypot`, `log`, `log10`, `max`, `min`, `pi`, `pow`, `radians`,
`round`, `sin`, `sinh`, `sqrt`, `tan`, `tanh`.

Rejected, with an error at the condition's line:

- `random()`: it is re-drawn on each evaluation, so it cannot describe a trace;
- a function registered at runtime (not a built-in);
- a built-in whose definition has been replaced at runtime.

Not every backend can evaluate functions: `native` can, MC2 cannot (section 9).

### 4.4 YAML quoting

Conditions are written as plain YAML scalars and need no quotes:
`always: level <= LIMIT`. TENNCell also accepts a leading `!` unquoted
(`never: !(x > 0)`), although YAML normally reserves it for tags. Two YAML
rules still apply:

- ` #` (a space, then `#`) starts a YAML comment: `always: x > 0 # note`
  checks `x > 0`.
- A YAML list or mapping is not a condition: `always: [x > 0]` or a nested
  `always:` block is an error ("nested properties are not supported in v1").

## 5. The time model: rows, steps and labels

### 5.1 A trace is a sequence of rows

A property is evaluated on a finite **trace**: rows `0, 1, ..., L-1`, each
giving a value to every column the property uses.

- **Row 0 is the initial state**, before any step has executed.
- Row `k` (`k >= 1`) is the state after `k` steps.

`nnc-verify` gets the rows in one of three ways:

| Source | Rows |
|---|---|
| `--steps N` (models without inputs) | the initial state, then `N` steps: `N + 1` rows |
| `--inputs FILE` (models with inputs) | the initial state, then one step per input record: `N` records give `N + 1` rows |
| `--trace FILE` (recorded) | one row per data line of the file |

Simulated rows contain every local variable (internal ones included) and
imported inputs/outputs as `alias__port`.

### 5.2 Inputs in simulated rows

In a simulated row `k >= 1`, an **input column holds the input of the step
that produced row `k`**, next to the state **after** that step. This holds even
when a rule consumes the input, and also for an imported module's input
(`alias.port`): its column holds the value the parent gave the child in that
step, for example a parent register's value from row `k - 1`. All imports are
given values from before the step, so an import reading another import's
output sees it one row later. With this run
of the controller from section 11:

| row | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| `req` (input) | 0 | 0 | 1 | 0 |
| `mode` | IDLE | IDLE | BUSY | BUSY |

Row 2 shows `req = 1` together with `mode = BUSY`, because the request was
already handled in that step. So a trigger `req > 0 && mode == ctrl.IDLE` never
holds on this run, and a response property using it passes without ever being
triggered. Write triggers about inputs in terms of the input alone
(`when: req > 0`), and allow offset `0` in the window when the reaction can be
immediate (`within: [0, n]`).

### 5.3 Offsets count rows

`after`, `within` and `from_step` count **rows**, not step labels and not time
units. `after: 1` means "the next row".

- `from_step: f` makes the property start at row `f`: rows before `f` are not
  checked, and triggers before `f` are ignored. Windows of
  `eventually` + `within` are relative to `f`.
- If `f` is past the end of the trace (`f >= L`), the range is empty; section
  7.3 gives the result for each kind.

### 5.4 Labels are only for reporting

Each row also has a **label**, used only in reports:

- simulated rows are labelled `0, 1, 2, ...`;
- in a recorded trace, a **first** column named `step`, `_step`, `time` or
  `Time` gives the labels; otherwise rows are labelled from `--first-step`
  (default 0);
- `--no-step-column` labels rows by position even when such a column exists,
  for logs whose step column is not a counter (PeP and Webots controller logs
  can write a constant there). The column stays usable as data.

Labels must be finite and strictly increasing. When all labels are whole
numbers and two consecutive labels differ by more than 1, `nnc-verify` warns,
because offsets still count rows:

```text
Warning: trace.csv: step labels jump from 0 to 5; after/within count rows, not steps
```

## 6. The property kinds

Notation used in this section:

- rows are `0 .. L-1`; `f` is `from_step`;
- `t` is a **trigger row**: a row `t >= f` where `T` holds;
- trace tables show one column per row; `1`/`0` mean true/false for the
  comparison involved;
- results are given as `status (trigger row, reported row)`.

The examples use variables `req`, `ack`, `level`, `err`, a constant
`LIMIT: 10`, and an FSM `ctrl` with states `IDLE` (0), `BUSY` (1) and `DONE` (2)
stored in `mode`.

Every trigger row opens its **own obligation**. Obligations of one property
are independent and may overlap; the property's result combines them
(section 8.2).

### 6.1 `always: P`

**Meaning.** `P` is true on every row `f .. L-1`.

**Fails** at the first row where `P` is false. It can never be left open at
the end of the trace, so `strict` and `weak` give the same result.

```yaml
- id: level_bounded
  always: level <= LIMIT
```

| row | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| `level` | 3 | 5 | 12 | 4 | 15 |

Result: `fail`, reported at row 2 (the first violation; row 4 is not reported).

**With `from_step`.** An initial row that is not yet meaningful can be
skipped:

```yaml
- id: level_positive
  always: level > 0
  from_step: 1
```

| row | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| `level` | 0 | 1 | 2 | 3 |

Result: `pass`. Without `from_step`, the same trace gives `fail` at row 0.
With `from_step: 5` on a 2-row trace, the range is empty and the result is
`pass`.

### 6.2 `never: P`

**Meaning.** `P` is false on every row `f .. L-1`; the same as
`always: !(P)`.

```yaml
- id: no_error
  never: err == 1
```

| row | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| `err` | 0 | 0 | 1 | 0 | 1 |

Result: `fail`, reported at row 2.

### 6.3 `eventually: P`

**Meaning.** `P` is true on at least one row `>= f`. There is no deadline:
this is a liveness property, which a finite trace can confirm but never
refute. If `P` has not been seen when the trace ends, the outcome depends on
`trace_semantics`: `strict` gives `fail` (reported at the last row), `weak`
gives `pending`.

```yaml
- id: reaches_done
  eventually: mode == ctrl.DONE
```

| row | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| `mode` | IDLE | BUSY | DONE | IDLE |

Result: `pass` (`P` is first seen at row 2; a passing result reports no row).

```yaml
- id: acknowledged
  eventually: ack == 1
```

| row | 0 | 1 | 2 |
|---|---|---|---|
| `ack` | 0 | 0 | 0 |

Result: `strict`: `fail`, reported at row 2 (the last row); `weak`: `pending`.

**`from_step` matters.** With `from_step: 2`, rows 0 and 1 do not count:

| row | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| `ack` | 0 | 1 | 0 | 0 |

Result: `strict`: `fail` at row 3; `weak`: `pending`. The `ack` on row 1 is
before the property starts.

### 6.4 `eventually: P` + `within: [a, b]`

**Meaning.** `P` is true on at least one row of the window `f+a .. f+b`. The
window is relative to `from_step` (row 0 by default).

- **Pass** as soon as `P` is seen in the window.
- **Fail** when the whole window lies inside the trace (`f+b <= L-1`) and `P`
  is false on every row of it. Reported at the window's last row, `f+b`.
- **Open** when the window extends past the end and `P` has not been seen yet:
  `strict` gives `fail` (reported at the last row), `weak` gives `pending`.

```yaml
- id: ack_soon
  eventually: ack == 1
  within: [1, 2]
```

| row | 0 | 1 | 2 | 3 | Result |
|---|---|---|---|---|---|
| `ack` (a) | 1 | 0 | 1 | 0 | `pass` (row 2 is in the window 1..2; row 0 is not) |
| `ack` (b) | 1 | 0 | 0 | 1 | `fail`, reported at row 2 (row 3 is too late) |
| `ack` (c) | 1 | 0 | | | `strict`: `fail` at row 1; `weak`: `pending` (the window reaches row 2, which does not exist) |

With `within: [0, 1]` and `from_step: 2`, the window is rows 2..3: on
`ack = 1 1 0 1 0` the result is `pass` (row 3).

If `f+a` is already past the end, nothing of the window is in the trace: the
result is `fail` (`strict`) or `pending` (`weak`).

### 6.5 `when: T` + `then: P` + `after: n`

**Meaning.** For every trigger row `t`, `P` is true on row `t+n`, exactly
that one row.

- **Fail** when `t+n` is in the trace and `P` is false there. The report gives
  the trigger `t` and the reported row `t+n`.
- **Open** when `t+n` is past the end: `strict` gives `fail` (reported at the
  last row), `weak` gives `pending`.
- With no trigger at all, the property passes.

```yaml
- id: ack_next
  when: req == 1
  then: ack == 1
  after: 1
```

| row | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| `req` | 1 | 0 | 1 | 0 |
| `ack` | 0 | 1 | 0 | 0 |

Result: `fail` (trigger row 2, reported row 3). The trigger at row 0 is
satisfied by row 1.

**A trigger on the last row.** With `req = 1 0 0 1` and `ack = 0 1 0 0`, the
trigger at row 3 needs row 4, which does not exist. `strict`: `fail` (trigger 3,
reported 3); `weak`: `pending`, with the open obligation at row 3.

**`after: 0`** checks the trigger row itself, which is a same-row implication:

```yaml
- id: busy_means_ack
  when: mode == ctrl.BUSY
  then: ack == 1
  after: 0
```

| row | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| `mode` | IDLE | BUSY | DONE | IDLE | BUSY |
| `ack` | 0 | 1 | 1 | 1 | 0 |

Result: `fail` (trigger row 4, reported row 4).

### 6.6 `when: T` + `then: P` + `within: [a, b]`

**Meaning.** For every trigger row `t`, `P` is true on at least one row of
`t+a .. t+b`.

- **Fail** when the window lies inside the trace and `P` is false on all of
  it. The report gives the trigger and the window's last row `t+b`.
- **Partial window.** If the window extends past the end but already contains
  a row where `P` holds, the obligation is satisfied.
- **Open** when the window extends past the end and `P` has not been seen yet:
  `strict` gives `fail` (reported at the last row), `weak` gives `pending`.

```yaml
- id: ack_within
  when: req == 1
  then: ack == 1
  within: [1, 3]
```

Overlapping triggers, both satisfied by the same row:

| row | 0 | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| `req` | 1 | 1 | 0 | 0 | 0 | 0 |
| `ack` | 0 | 0 | 0 | 1 | 0 | 0 |

Result: `pass`. The window of trigger 0 is rows 1..3, the window of trigger 1 is
rows 2..4, and both contain row 3.

A partial window that already contains `P` (`req = 0 0 1 0`, `ack = 0 0 0 1`):
the window of trigger 2 is rows 3..5, row 3 has `ack = 1`, and the result is
`pass`, even with `strict`.

An open window (`req = 0 0 0 1 0`, `ack = 0 0 0 0 0`): the window of
trigger 3 is rows 4..6. `strict`: `fail` (trigger 3, reported 4, the last row);
`weak`: `pending`.

One failed and one open obligation, with `within: [1, 2]`:

| row | 0 | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| `req` | 1 | 0 | 0 | 0 | 1 | 0 |
| `ack` | 0 | 0 | 0 | 1 | 0 | 0 |

Trigger 0 fails (its window 1..2 has no `ack`); trigger 4 is open (window
5..6). Result under both semantics: `fail` (trigger 0, reported 2), because a
failure is worse than `pending` (section 8.2).

### 6.7 `when: T` + `then_always: P` [+ `after: n`]

**Meaning.** For every trigger row `t`, `P` is true on **every** row from
`t+n` to the end of the trace. `after` defaults to `0` (starting at the
trigger row itself).

- **Fail** at the first row `>= t+n` where `P` is false. The report gives the
  trigger and that row.
- **Hold throughout.** Rows past the end are never checked, so nothing can be
  left open: a trigger so close to the end that `t+n` does not exist **passes,
  even with `strict`**. `strict` and `weak` always agree.

```yaml
- id: level_stays_positive
  when: ack == 1
  then_always: level > 0
```

| row | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| `ack` | 0 | 1 | 0 | 0 | 0 |
| `level` | 0 | 2 | 3 | 0 | 1 |

Result: `fail` (trigger row 1, reported row 3). Row 0 is before the trigger
and is not checked.

With `after: 1` (`when: req == 1`, `then_always: ack == 1`):

| row | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| `req` | 1 | 0 | 0 | 1 |
| `ack` | 0 | 1 | 1 | 0 |

Result: `fail` (trigger 0, reported 3): from row 1 on, `ack` must stay 1, and
row 3 breaks it. The trigger at row 3 needs rows from 4 on, which do not exist,
so it adds nothing.

With `after: 2`, `req = 0 0 0 1` and `ack = 0 0 0 0`: the only trigger is row
3, `t+2 = 5` is past the end, and the result is `pass` under both semantics.

### 6.8 `cover: P`

**Meaning.** `P` is true on at least one row `>= f`. The result is `covered`
or `not_covered`. A cover property is **observed, not asserted**: it never
fails and never affects the exit status. It is not affected by
`trace_semantics`.

```yaml
- id: fills_up
  cover: level >= LIMIT
```

| row | 0 | 1 | 2 | 3 | Result |
|---|---|---|---|---|---|
| `level` | 0 | 4 | 10 | 2 | `covered` |
| `level` | 0 | 4 | 9 | 2 | `not_covered` |

Use `cover` to check that a run actually exercises the behavior the other
properties talk about: a response property whose trigger never fires passes
without testing anything.

## 7. End of trace: `strict` and `weak`

### 7.1 Two families of obligations

- **Hold throughout:** `always`, `never`, `then_always`. They pass if no
  violation appears before the trace ends. The end of the trace never creates
  a failure.
- **Must happen:** `eventually`, `within` windows, and `then` with `after`. An
  obligation is **open** when the trace ends before it could be decided: its
  target row or window lies past the last row, or `eventually` has not been
  met yet.

### 7.2 Resolving open obligations

`verification.trace_semantics` decides what an open obligation means:

- `strict` (default): it **fails**. This is the usual finite-trace reading and
  matches MC2. The failure is reported at the last row.
- `weak`: it is **pending**: neither proved nor refuted by this trace.

A violation seen inside the trace is a `fail` under both settings.

A backend section may override the setting for that backend only:

```yaml
verification:
  trace_semantics: weak
  backends:
    mc2:
      trace_semantics: strict
```

### 7.3 Summary per kind

| Kind | Violation inside the trace | Open at the end: `strict` / `weak` | `f >= L` (empty range): `strict` / `weak` |
|---|---|---|---|
| `always P` | first row with `P` false | never open | `pass` / `pass` |
| `never P` | first row with `P` true | never open | `pass` / `pass` |
| `eventually P` | none: cannot be refuted | `fail` / `pending` | `fail` / `pending` |
| `eventually P within [a,b]` | window inside the trace, no `P` | `fail` / `pending` | `fail` / `pending` |
| `when T then P after n` | `P` false at `t+n` | `fail` / `pending` | `pass` / `pass` (no trigger) |
| `when T then P within [a,b]` | window inside the trace, no `P` | `fail` / `pending` | `pass` / `pass` |
| `when T then_always P after n` | first row `>= t+n` with `P` false | never open | `pass` / `pass` |
| `cover P` | not applicable | `not_covered` / `not_covered` | `not_covered` / `not_covered` |

## 8. Results and reporting

### 8.1 Statuses

| Status | Meaning | Fails the run (exit 1)? |
|---|---|---|
| `pass` | every obligation is satisfied | no |
| `fail` | some obligation is violated (or open, with `strict`) | **yes** |
| `pending` | no violation, some obligation still open (`weak` only) | no |
| `covered` / `not_covered` | `cover` result | no |
| `skipped` | the property is not meant for `native` (section 9) | no |

### 8.2 Combining obligations

A property's result is the **worst** of its obligations, in the order
`fail` > `pending` > `pass`.

### 8.3 Which row is reported

Each result keeps two positions, each as a row number and a label:

- **trigger**: the row where the failed obligation was opened (trigger kinds
  only);
- **reported**: the row where the failure became known:

| Kind | Reported row |
|---|---|
| `always`, `never`, `then_always` | the first violating row |
| `then` + `after: n` | `t+n` |
| `then` + `within: [a, b]` | `t+b`, the end of the window |
| `eventually` + `within: [a, b]` | `f+b`, the end of the window |
| any open obligation under `strict` | the last row |

When several obligations fail, the one with the **earliest reported row** is
reported; ties go to the earliest trigger. A `pending` result lists every open
obligation (the trigger row for trigger kinds, "end of trace" otherwise). The
table shows the first 10 of them and a count; JSON output lists them all.

### 8.4 Output of `nnc-verify`

The table has one line per property:

```text
id                          kind             result   trigger    reported     open
level_bounded               always           pass
request_served              response_within  fail     row 9 (9)  row 10 (10)
fills_up                    cover            covered
```

`row 9 (9)` is a row number followed by its label. `--json` prints the same
data with the fields `id`, `kind`, `status`, `trigger_row`, `trigger_label`,
`reported_row`, `reported_label` and `open_obligations`.

Exit status: `0` when no property fails, `1` when a property fails or an
error occurs (section 10), `2` for command-line errors.

## 9. Targets and backends

### 9.1 `targets`

| `targets` | Meaning |
|---|---|
| absent | the property is meant for every backend that supports it |
| `[native]` | only checked by `nnc-verify` |
| `[mc2]` | only translated to MC2 |
| `[native, mc2]` | both |

Accepted names are `native`, `mc2` and `sva`. `prism`, `spin`, `english` and
`custom` are reserved and rejected; any other name is an error.

Each tool uses only the properties meant for it:

| Situation | `nnc-verify` (`native`) | `nnc-gen -t mc2` |
|---|---|---|
| property meant for it, supported | checked | translated |
| property for other backends only | reported as `skipped` | omitted, silently |
| no `targets`, uses a construct the backend lacks | not applicable (`native` supports everything) | omitted, with a warning |
| `targets` lists it, uses a construct the backend lacks | not applicable | **error** |

### 9.2 `native`

Supports every kind and every allowed function. It is the **reference
semantics**: this document describes its behavior, and other backends are
tested against it.

### 9.3 `mc2`

Each property becomes one MC2 query `P=?[ ... ]` in `<stem>.mc2.pltl`,
written after the raw MC2 entries; its ID goes to `<stem>.mc2.ids` and its
columns to `<stem>.mc2.columns`.

- **No function calls.** A property using one is skipped with a warning, or is
  an error if its `targets` list `mc2`:

  ```text
  generic verification properties skipped for MC2: shape (calls abs; MC2 queries cannot call functions)
  ```

- **IDs.** An emitted property ID must differ from every raw MC2 entry ID. A
  property that is not emitted for MC2 (for example `targets: [native]`) may
  reuse a raw ID.
- **Conditions** are rewritten into MC2 syntax with full parentheses:
  variables become `[name]`, imported ports `[alias__port]`, constants and FSM
  states numbers; `&&` becomes `^`, `||` becomes `V`, `!` becomes `¬(...)`,
  `==` becomes `=`.

  ```text
  always: !(err == 1) && level >= 0 || mode == ctrl.DONE
  P=?[G(((¬(([err] = 1)) ^ ([level] >= 0)) V ([mode] = 2)))]
  ```

- **Kinds** use `G`, `F` and nested `X` (one `X` per row). Some translations:

  | Property | MC2 query |
  |---|---|
  | `always: level <= LIMIT` | `P=?[G(([level] <= 10))]` |
  | `never: err == 1` | `P=?[G(¬(([err] = 1)))]` |
  | `eventually: ack == 1`, `from_step: 2` | `P=?[X(X(F(([ack] = 1))))]` |
  | `always: level > 0`, `from_step: 1` | `P=?[(¬(X(true)) V X(G(([level] > 0))))]` |
  | `eventually: ack == 1`, `within: [1, 2]` | `P=?[X((([ack] = 1) V X(([ack] = 1))))]` |
  | `when: req == 1`, `then: ack == 1`, `after: 1` | `P=?[G((¬(([req] = 1)) V X(([ack] = 1))))]` |
  | `when: ack == 1`, `then_always: level > 0` | `P=?[G((¬(([ack] = 1)) V G(([level] > 0))))]` |
  | `cover: level >= LIMIT` | `P=?[F(([level] >= 10))]` |

  `¬X^k(true)` ("the trace ends within `k` rows") is added where needed, so
  that `from_step` past the end and the end-of-trace cases give the same
  answer as `native`. The complete table is in `docs/verification.md`, section
  7.3.1.
- **Reading the result.** MC2 prints `1.0` where `native` reports `pass` or
  `covered`, and `0.0` for `fail` or `not_covered`.
- **`weak` is approximated.** MC2 has no `pending`. With `weak`, an open
  bounded `eventually` or response obligation counts as satisfied (`1.0`), and
  an unmet unbounded `eventually` gives `0.0`. `nnc-gen` warns about both. With
  `after: 0`, a response `within: [0, 0]`, or a bounded `eventually` with
  `within: [0, 0]` **and** `from_step: 0`, nothing can stay open, the query is
  exact, and there is no warning. (A bounded `eventually` with `from_step > 0`
  can still be open when the trace ends before `from_step`.)
- MC2 reads its own trace file: the variables the queries use must be in it
  (see the MC2 section of `README.md`).

### 9.4 `sva`

The SVA backend checks the generated fixed-point RTL, not the floating-point
Python model. It generates files only; it does not invoke a simulator or a
formal tool.

For a model with inputs, give the simulation records with `--sva-inputs`.
For an autonomous model, give the number of steps with `--sva-steps`:

```text
nnc-gen model.yaml -t sva --sva-inputs inputs.csv -o out
nnc-gen model.yaml -t sva --sva-steps 20 -o out
cd out
iverilog -g2012 -o sim.vvp *.sv
vvp sim.vvp
```

Monitor style (the default) prints `SVA_RESULT` and `SVA_OPEN` records with the
same finite-trace statuses and row meanings as `nnc-verify`. Input values are
encoded for the RTL in `<stem>_inputs.hex`; `<stem>_inputs_decoded.csv` contains
the quantized values to use for a fair native comparison. Fixed-point rounding
and overflow can still make RTL and native results differ. `--sva-style
concurrent` instead emits `assert property`/`cover property` for tools with
full concurrent-SVA support; it is simulation-only, strict-only, and has no
native-equivalent result recorder.

Formal mode writes the checker, bind file and `<stem>.sby`:

```text
nnc-gen model.yaml -t sva --sva-mode formal --sva-depth 20 -o out
cd out
sby -f model.sby bmc
sby -f model.sby cover
sby -f model.sby prove_kind
sby -f model.sby prove_pdr
sby -f model.sby live
```

`bmc` and `cover` explore property rows `0..D-1`, where `D` is
`--sva-depth`. `prove_kind` and `prove_pdr` check safety properties for runs of
any length; only `PASS` means proved. The `live` task checks unbounded
`eventually` properties and requires the `suprove` engine. If `suprove` is not
installed, run the other tasks by name rather than running every task at once.
Formal checks have no strict/weak end-of-trace distinction: an obligation whose
window extends beyond the bounded horizon is not a failure. Input ranges under
`verification.environment` become assumptions on the live RTL input ports.

The task status means:

| Task | `PASS` | `FAIL` / `UNKNOWN` |
|---|---|---|
| `bmc` | no assertion failure was found in rows `0..D-1` | `FAIL`: a bounded counterexample was found |
| `cover` | every reachable cover objective was reached within the depth | `FAIL`: at least one objective was not reached within the depth |
| `prove_kind` | all safety assertions were proved by k-induction | `UNKNOWN`: the chosen induction length was insufficient; increase `--sva-depth` or try PDR |
| `prove_pdr` | all safety assertions were proved by PDR | anything other than `PASS` is not a proof |
| `live` | every unbounded `eventually` property holds on every infinite run | `FAIL`: at least one does not; the aggregate task does not identify which one |

Run one task at a time while diagnosing a model. A failing assertion makes the
combined BMC/proof result fail; similarly, all liveness properties share one
`live` result. Temporarily target or retain one property when the aggregate
result does not identify it. See `docs/sva_workflows.md` for complete passing,
failing, cover and replay tutorials with expected output.

A BMC counterexample or cover witness can be turned into a self-checking RTL
simulation:

```text
nnc-gen model.yaml -t sva --sva-replay out/model_bmc/engine_0/trace.yw -o replay
```

The generated testbench reports `SVA_REPLAY reproduced on row N`, or fails if
the expected failure/cover is not reproduced. `nnc-gen` still does not run the
simulator. Run `nnc-verify` on the decoded replay inputs to see whether the
floating-point model agrees with the RTL; disagreement is diagnostic, not a
replay failure.

Function calls, variable-by-variable multiplication, non-signal observations,
and bounds above `--sva-max-bound` are unsupported. Such a property is an error
when it explicitly targets `sva`, and otherwise is skipped with a warning.
Raw entries under `verification.backends.sva.raw` are inserted at checker
module scope after `${name}` placeholders are bound to checker-visible signals
or encoded constants; their tool compatibility is the user's responsibility.
The complete file, scheduling, tool-support and replay contracts are in
`rules.md`, section "SVA Backend". A runnable example is
`examples/verification/sva_flag.yaml`; the deliberately failing replay
example is `examples/verification/sva_failure.yaml`. Their complete workflows
are in `docs/sva_workflows.md`.

## 10. Errors that are not failures

These stop `nnc-verify` with exit status `1` and an error message. They are
never reported as a property `fail`:

- **Configuration errors**, with the YAML file and line: an invalid kind
  combination, a bad bound, an unknown name, a forbidden function, a duplicate
  ID.
- **A missing column** in a recorded trace that a checked property uses:
  `trace has no column 'x'`. Columns used only by skipped properties may be
  missing.
- **A non-finite value** (`nan`, `inf`) in a column a checked property uses,
  reported with the column, row and label.
- **An evaluation error**, for example `sqrt` of a negative value:

  ```text
  Error: Property 'root': evaluating the 'always' condition at row 1 (label 1): ...
  ```

## 11. A complete example

A request/acknowledge controller. A request moves it from `IDLE` to `BUSY`;
in `BUSY` it fills `level` up to 3, then raises `ack` and goes to `DONE`, then
back to `IDLE`.

```yaml
constants:
  LIMIT: 10

cells:
  - id: 1
    contents:
      - req = 0
      - ack = 0
      - level = 0
      - mode = 0
    input: [req]
    output: [ack, level, mode]

fsm:
  - name: ctrl
    variable: mode
    initial: IDLE
    states:
      - IDLE:
          rules:
            - if: req > 0
              then:
                - BUSY -> mode
                - ack * 0 -> ack
      - BUSY:
          rules:
            - if: level >= 3
              then:
                - DONE -> mode
                - 1 -> ack
              else:
                - level + 1 -> level
      - DONE:
          rules:
            - IDLE -> mode
            - level * 0 -> level

verification:
  trace_semantics: strict
  properties:
    - id: level_bounded
      always: level <= LIMIT
    - id: ack_only_when_done_or_idle
      never: ack == 1 && mode == ctrl.BUSY
    - id: request_served
      when: req > 0
      then: ack == 1
      within: [0, 6]
    - id: done_returns_to_idle
      when: mode == ctrl.DONE
      then: mode == ctrl.IDLE
      after: 1
    - id: fills_up
      cover: level >= 3
```

Input file `in.csv` (one column `req`, ten records):

```text
req
0
1
0
0
0
0
0
0
1
0
```

The simulated trace (`nnc-verify handshake.yaml --inputs in.csv`):

| row | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `req` | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| `mode` | IDLE | IDLE | BUSY | BUSY | BUSY | BUSY | DONE | IDLE | IDLE | BUSY | BUSY |
| `level` | 0 | 0 | 0 | 1 | 2 | 3 | 3 | 0 | 0 | 0 | 1 |
| `ack` | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 1 | 0 | 0 |

Result with `strict`:

```text
id                          kind             result   trigger    reported     open
level_bounded               always           pass
ack_only_when_done_or_idle  never            pass
request_served              response_within  fail     row 9 (9)  row 10 (10)
done_returns_to_idle        response_after   pass
fills_up                    cover            covered
```

The request at row 2 is acknowledged at row 6 (offset 4, inside `[0, 6]`).
The second request, at row 9, needs `ack` in rows 9..15, but the run ends at
row 10: with `strict` this open obligation fails, reported at the last row,
and `nnc-verify` exits with `1`. With `trace_semantics: weak`, the same run
gives `request_served  response_within  pending  ...  row 9 (9)` in the
`open` column, and exit status `0`.

For MC2 (`nnc-gen handshake.yaml -t mc2 -o out`), `request_served` becomes:

```text
P=?[G((¬(([req] > 0)) V (([ack] = 1) V X((([ack] = 1) V X((([ack] = 1) V X((([ack] = 1) V X((([ack] = 1) V X((([ack] = 1) V X(([ack] = 1)))))))))))))))]
```

`nnc-gen` also warns that `req` is not a root output: `nnc-sim` traces contain
only outputs, so an MC2 trace for this query must come from another source, or
`req` must be declared as an output.

A larger worked example, including the MC2 run on a recorded trace, is
`examples/verification/fsm_counter_mc2.yaml`.

## 12. Patterns and limitations

### 12.1 Common patterns

| Intent | Property |
|---|---|
| Invariant | `always: level <= LIMIT` |
| Mutual exclusion | `never: valve_in == 1 && valve_out == 1` |
| Reach a state | `eventually: mode == ctrl.DONE` |
| Reach it in time | `eventually: mode == ctrl.DONE` + `within: [0, 20]` |
| Next-row reaction | `when: T` + `then: P` + `after: 1` |
| Same-row implication | `when: T` + `then: P` + `after: 0` (or `always: !(T) \|\| P`) |
| Bounded response | `when: T` + `then: P` + `within: [1, 10]` |
| Latching ("once set, stays set") | `when: done == 1` + `then_always: done == 1` |
| Stability after a settling time | `when: T` + `then_always: P` + `after: n` |
| Ignore start-up | add `from_step: n` |
| Check the run exercises a case | `cover: mode == ctrl.BUSY` |

### 12.2 What cannot be expressed (v1)

- **Nesting**: `always` inside `eventually`, and so on. There is no `formula:`
  key yet; see `docs/verification.md`, section 4.7.
- **"Until"** (`P` holds until `Q`), and **past-time** operators ("`P` was
  true on the previous row"). A previous value can be expressed only if the
  model stores it in a variable.
- **Edges** (`T` becomes true): a trigger opens an obligation on **every**
  row where it holds, not only on the first. Store the previous value in the
  model and trigger on `x == 1 && x_prev == 0` if needed.
- **Probabilities** (`probability`) and input distributions.
- **Time units**: offsets count rows; step labels are not used for timing.

## 13. Quick reference

Schematic (alternatives are listed together; a real entry has one kind):

```yaml
verification:
  trace_semantics: strict | weak            # default strict
  properties:
    - id: name                              # required, unique identifier
      description: text                     # optional
      targets: [native, mc2, sva]           # optional; default: all that support it
      from_step: 0                          # optional; first row checked

      # exactly one of:
      always: P
      never: P
      eventually: P                         # optionally + within: [a, b]
      when: T
      then: P                               # + exactly one of after: n | within: [a, b]
      when: T
      then_always: P                        # + optional after: n (default 0)
      cover: P
```

| Kind | Satisfied when | Open at the end (`strict` / `weak`) |
|---|---|---|
| `always P` | `P` on every row `>= f` | never open |
| `never P` | `P` on no row `>= f` | never open |
| `eventually P` | `P` on some row `>= f` | `fail` / `pending` |
| `eventually P within [a,b]` | `P` on some row of `f+a .. f+b` | `fail` / `pending` |
| `when T then P after n` | each `T` at `t`: `P` at `t+n` | `fail` / `pending` |
| `when T then P within [a,b]` | each `T` at `t`: `P` on some row of `t+a .. t+b` | `fail` / `pending` |
| `when T then_always P after n` | each `T` at `t`: `P` on every row `>= t+n` | never open |
| `cover P` | `P` on some row `>= f` | `not_covered` |
