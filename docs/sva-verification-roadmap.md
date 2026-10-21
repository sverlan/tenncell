# Property-based Formal Verification Roadmap

**Status: design direction, not an implementation contract.** This roadmap
records agreed direction, proposed phases and unresolved questions. Current
contracts remain in [verification.md](verification.md),
[generic_properties.md](generic_properties.md) and [../rules.md](../rules.md).

## Current behavior

- Structured properties have a backend-neutral representation (`GenericProperty`
  and `BoundProperty`). The `native` checker evaluates traces; the `sva` backend
  generates either procedural finite-state monitors or concurrent SVA.
- Monitor style supports simulation and Yosys/SymbiYosys formal generation.
  Concurrent style is currently simulation-only, requires strict trace semantics,
  and depends on the simulator's supported SVA subset.
- Formal generation already provides `bmc`, `cover`, `prove_pdr` (`abc pdr`) and
  `prove_kind` (`smtbmc` k-induction) tasks. Unbounded `eventually` uses a separate
  `live` task (`aiger suprove`). TENNCell generates artifacts; users run the tools.
- Environment ranges become assumptions on live root input ports. Formal reset
  is applied initially and cannot reassert. Richer structured assumptions and
  configurable reset policies are not implemented.
- Raw SVA is emitted after model-placeholder binding; TENNCell does not parse
  its temporal syntax or invoke an external SVA-lowering tool.
- Regression tests compare monitor simulation with the native trace checker.
  Concurrent SVA has limited simulator coverage; general SVA-to-monitor
  equivalence has not been established. BMC/cover witness replay already exists.

Implementation anchors: `src/nnc/verification/config.py`,
`generic_properties/binding.py`, `sva_concurrent.py`, `sva_monitors.py`,
`sva_checker.py` and `sva_formal.py` (the latter paths are relative to
`src/nnc/verification/`). Test contracts include
`tests/contracts/functional/sva_simulation.md` and `sva_sby.md`.

## Agreed design direction

### One restricted language, two generation paths

The same structured TENNCell property language should serve SV/SVA
testbench/simulation verification and Yosys-based formal verification, even when
execution backends differ. Its deliberate restriction is a design feature:
clear synchronous semantics, predictable finite-state monitors and useful
BMC/PDR behavior. It should hide unsupported or difficult temporal constructs,
and should not evolve into a general LTL or arbitrary SVA frontend.

Preferred architecture:

```text
TENNCell property IR
    -> SVA backend -> simulator / SVA-capable verification tool
                   -> external SVA lowering -> Yosys formal verification
    -> native monitor backend -> Yosys formal verification
```

These are alternative translations of the same IR. SVA serves testbench
assertions, readable/exportable assertions and SVA-capable tools. Generated SVA
also provides a formal-verification path through an external tool that lowers
its supported subset for Yosys; this option applies to structured properties as
well as raw SVA. Native monitor generation serves direct Yosys formal checks,
predictable finite-state lowering and control over state that works well with
PDR. Here, "native monitor" means
generated RTL monitor logic, distinct from the current `native` trace checker;
the architecture does not require renaming today's CLI backends.

Both translations must follow the same documented semantics and gain regression
tests for semantic equivalence on their supported overlap. Ordinary structured
properties must not require the external SVA-lowering tool.

Use one shared structured language, with the verification role selected by its
group under `verification`: `properties:` for DUT assertions, `assumptions:` for
environment obligations, and `cover:` for existential reachability goals. No
per-entry role field is needed. These groups should lower to the same property
IR with an explicit role, sharing conditions and temporal semantics while
retaining role-specific validation, reporting and backend capability checks.
This grouping is proposed syntax; currently covers are entries in `properties`.
Sharing the language does not require every advanced construct to be supported
in every role or backend immediately; unsupported combinations must be explicit.

Keep normal temporal obligations safety-oriented and finite-memory wherever
possible. Prefer bounded response windows when progress is required; reserve
unbounded liveness for advanced cases. For PDR, the useful design property is
safety with a finite-state monitor, not necessarily a finite temporal horizon.
`always P`, `never P` and existing `then_always` can have indefinite duration
without introducing the liveness requirement of unbounded `eventually`.

Normal forms include same-cycle `when A then B`, responses after N cycles or
within [N, M], and `eventually P within N`; bounded persistence would need its
own specification. Reachability goals remain expressible through covers. These
are conceptual forms, not proposed YAML syntax. Advanced liveness has different
fairness and solver requirements.

### Raw SVA remains an independent escape hatch

```text
structured TENNCell property -> native TENNCell SVA or monitor generation
                               (including external lowering of generated SVA)
raw SVA                     -> direct simulator use, or
                            -> external SVA lowering -> Yosys
```

Retain raw SVA for properties outside the structured language. Simulation may
use it directly; Yosys flows may use the existing, separately maintained
SVA-to-Yosys/monitor lowering tool. Integration with TENNCell is proposed work,
not current automatic behavior. Raw-SVA support need not define or constrain the
structured language.

**YAML caveat:** raw SVA containing `#` / `##` must use quoted strings or,
preferably, a block scalar (`code: |`). In plain scalars, `#` after whitespace
can start a YAML comment and remove text before TENNCell sees it:

```yaml
code: |
  assert property (@(posedge clk) req |-> ##[1:4] ready);
```

### Controller proofs and environment contracts

Start with FSMs, protocol controllers, flags, counters, bounded responses and
safety invariants. Distinguish controller correctness from plant/environment
correctness: claims about physical evolution may require an explicit plant or
environment model.

A major next step is a small controller-oriented environment assumption language,
starting from existing ranges. Candidate contracts are input ranges/enums,
maximum delta/slew, bounded stability, minimum pulse width, minimum event
interval, mutually exclusive inputs, no new request while a transaction is
pending, bounded request-to-response behavior, and reset/reassertion policy.

Assumptions must describe real environment/interface obligations, never assume
DUT correctness. Signal ownership matters: a response supplied by the environment
may be assumed; a response owed by the controller must be asserted. Prefer
`request -> ready within N cycles` to `request -> eventually ready` when the
engineering interface has a realistic bound. Favor bounded contracts over
unbounded fairness.

| Meaning | Formal construct |
|---|---|
| Controller/DUT obligation | `assert` |
| Environment obligation | `assume` |
| Reachability or sanity scenario | `cover` |

The shared environment contract has different uses depending on execution:

| Context | Intended treatment of an environment contract |
|---|---|
| Formal | Emit `assume` to constrain explored executions. |
| Simulation | Check stimulus legality and/or guide stimulus generation. |

An assumption cannot constrain an existing ordinary testbench by itself.
Simulation must report environment-contract violations separately from DUT
assertion failures; stimulus generation requires an explicit integration.
These simulation uses of structured assumptions are planned behavior.

Add assumption sanity checking: contradictory or overly restrictive assumptions
can make a formal PASS meaningless. Cover important states/events and property
triggers under the same assumptions. Covers provide reachability evidence, not
a general guarantee that the environment contract is adequate. Future reporting
could distinguish property proof results, assumption satisfiability/reachability,
and cover reachability, with bounded horizons and unknown results explicit.

### Automatic sanity covers

Keep explicit `cover:` entries for engineering scenarios. Plan a small default
set of trigger and harness sanity covers, with successful-response covers as
additional, optional diagnostics:

| Source | Generated reachability goal | Policy |
|---|---|---|
| Triggered assertion | Its antecedent can occur under the assumptions. | Default sanity cover |
| Environment response assumption | The DUT can trigger the environment obligation. | Default sanity cover |
| Formal harness | Execution can leave reset and reach an active checking cycle. | Default sanity cover |
| Bounded response assertion or assumption | A trigger and its successful response can occur within the specified window. | Optional diagnostic |

For `when A then B within [1, 1000]`, covering A may be a useful inexpensive
vacuity check, while finding a full successful transaction can cost substantially
more. Do not require successful-response covers for every property; their scope
and search budgets should be configurable.

Generated covers must follow the source property's sampling, reset and window
semantics. Covering a consequent alone does not establish a valid response to a
trigger. Report generated covers separately from user covers and associate each
with its source property, assumption or harness rule.

An unreachable trigger is a diagnostic, not automatically an error: possible
causes include restrictive assumptions, unreachable DUT behavior, an insufficient
search depth or an intentionally inactive property. A successful transaction
witness does not prove correctness or establish that the assumptions are
appropriate. Avoid automatically covering every FSM state or range endpoint;
some are intentionally unreachable.

For example, report an assertion as proved alongside a reachable trigger (and a
successful response if that optional diagnostic ran), or alongside "trigger not
reached within 20 cycles" and a possible-vacuity diagnostic. Keep bounded
non-reachability, unknown results and diagnostics not run explicit. These
diagnostics help interpret a proof without changing its result. Automatic cover
generation and reporting are future work.

### Bounded-change assumptions

Ranges alone allow a solver to jump between legal extremes on consecutive
cycles, even when that change is physically or architecturally impossible.
Consider bounded-change contracts for environment-controlled inputs:

```text
abs(x(t+1) - x(t)) <= max_delta
```

This suits temperatures, positions, velocities, sensor readings, voltages and
other slowly varying physical inputs. A possible structured form is:

```yaml
environment:
  temperature:
    range: [-40, 125]
    max_delta: 2                   # Proposed; not implemented
```

The intended lowering is an assumption relating each current sampled value to
the previous sampled value. For example, 20 to 22 is allowed, while 20 to 23 is
excluded despite both values being in range. These bounds must describe genuine
environment characteristics, never be chosen merely to make a proof succeed.

For fixed-point signals, use the RTL's numeric encoding and scale, but perform
the generated difference check with widened arithmetic. Conceptually:

```text
-delta_encoded <= widen(x_encoded) - widen(prev_x_encoded) <= delta_encoded
```

Extend operands appropriately for their signedness to a common signed width
that can represent the full difference and bounds before subtracting. Avoid
fixed-width `abs(x - prev_x)`, whose subtraction or absolute value can overflow,
including at the minimum signed value. Bound quantization and exact width rules
still need specification; the first sample and reset also need defined
history-validity rules.

Later, asymmetric bounds may be useful when changes are faster in one direction:

```yaml
max_rise: 3                        # Proposed alternative to max_delta
max_fall: 10
```

These would bound increases by 3 and decreases by 10 per sampled cycle. Their
combination with `max_delta`, if permitted, remains to be specified.

### Restricted assumption properties

Assumptions should use the same deliberately restricted structured language as
assertions, rather than arbitrary LTL. Candidate forms are:

| Form | Environment contract |
|---|---|
| `always CONDITION` | Invariants and legal combinations of input values |
| `when A then B` | Immediate, same-cycle relationships |
| `when A then B after N` | Fixed-latency obligations |
| `when A then B within [N, M]` | Bounded-response obligations |
| `range`, `max_delta`, `stable_for` | Value bounds, bounded change and stability |
| `min_pulse`, `min_interval`, `mutually_exclusive` | Pulse, event-spacing and input-exclusion constraints |

Dedicated constraints are preferable when clearer than a temporal formula; their
exact syntax and semantics remain proposals. Where meaningful, these constraints
should also be usable as assertions: an input slew limit may be assumed, while
an output slew limit may be asserted. The `environment` section can remain
convenient shorthand for assumptions. For example, in this independent
sketch `dut_request` is a DUT output and `peripheral_ready` an environment input:

```yaml
assumptions:                       # Proposed; not implemented
  - id: peripheral_response
    when: dut_request == 1
    then: peripheral_ready == 1
    within: [1, 8]
```

Every DUT request would require the environment to supply ready between one and
eight cycles later, inclusive. Make signal ownership a core validation rule for
structured assumptions: allow DUT outputs as triggers or context for environment
obligations, but require the constrained response to belong to the environment.
Reject assumptions that impose DUT correctness obligations. Apply ownership
validation to dedicated input constraints as well; mixed-signal invariants need
explicit rules for identifying what they constrain. These checks are planned,
and cannot by themselves establish that an environment contract is realistic.
`DUT request -> environment acknowledge within 8 cycles` is an environment
contract; `DUT request -> DUT enters DONE` must remain an assertion.

Prefer a realistic finite bound, such as `request -> ready within 32 cycles`,
over unbounded `request -> eventually ready`: the bounded contract has a clear
engineering meaning and normally lowers to a finite-state safety monitor.
Assumptions must share property semantics for reset, cycle boundaries,
overlapping triggers and inclusive bounds, consistently across SVA and native
monitor generation.

### Solver portfolio

Use BMC first for short counterexamples, PDR/IC3 as the preferred unbounded safety
method for controller-heavy designs, and k-induction as an additional method.
Consider SMT/bit-vector engines where arithmetic-heavy fixed-point logic benefits.
For the current Yosys/SymbiYosys flow, `abc pdr` is a strong default candidate for
controller safety proofs. Benchmark representative TENNCell models before fixing
defaults; no single solver implementation is a permanent commitment. A bounded
PASS must remain distinguishable from an unbounded proof.

## Illustrative specifications and intended results

The following fragment is a **syntax proposal, not a runnable model or final
schema**. In particular, the `verification.assumptions` and `verification.cover`
groups are not currently accepted. All three groups reuse the same structured
condition and temporal forms; their placement selects assertion, assumption or
cover interpretation.

Consider a controller with environment inputs `request` and `ready`, and DUT
outputs `busy`, `issue` and `done`. A request is accepted on a row where
`request == 1 && busy == 0`. The environment owes `ready` after the DUT issues
a command; the DUT owes completion after accepting a request. For this sketch,
checks start after the initial reset, which does not reassert.

```yaml
verification:
  environment:
    request: { range: [0, 1] }
    ready: { range: [0, 1] }

  assumptions:                       # Proposed; not implemented
    - id: no_request_while_busy
      always: request == 0 || busy == 0
    - id: environment_responds
      when: issue == 1
      then: ready == 1
      within: [1, 3]

  properties:
    - id: completes_in_time          # DUT assertion
      when: request == 1 && busy == 0
      then: done == 1
      within: [1, 5]
    - id: completion_is_idle         # Same-cycle safety assertion
      when: done == 1
      then: busy == 0
      after: 0

  cover:                             # Proposed separate group
    - id: can_accept                 # Assumption sanity cover
      eventually: request == 1 && busy == 0
      within: [0, 20]
    - id: can_finish
      eventually: done == 1 && busy == 0
      within: [0, 20]
```

| Entry | Intended formal result |
|---|---|
| Input ranges | Assume only binary input values; this does not prove a DUT obligation. |
| `no_request_while_busy` | Exclude environment traces with `request == 1` while `busy != 0`; allow an idle request. |
| `environment_responds` | Every issue at row t requires ready on some row t+1 through t+3, inclusive. A missing response excludes that trace. |
| `completes_in_time` | Prove completion at t+1 through t+5 for every accepted request at t under the assumptions; otherwise return a counterexample. |
| `completion_is_idle` | Prove busy is zero on every completion row; simultaneous done and busy produces a counterexample. |
| `can_accept`, `can_finish` | Find witnesses reaching acceptance and idle completion on rows 0 through 20 under the same assumptions. These are existential checks, not proofs of inevitable progress. |

For example, acceptance at row 0, issue at row 1, ready at row 3 and idle
completion at row 4 satisfy these obligations. If no completion occurs on rows
1 through 5, the completion assertion fails at row 5 even if done occurs at row
6. A ready pulse only on row 1 does not satisfy the issue's response window of
rows 2 through 4. Each trigger creates an independent obligation; one response
may satisfy several obligations when their valid windows overlap.

A correct controller should obtain safety proofs and reachable covers; the
fragment alone cannot guarantee those results without a DUT model. With a short
BMC horizon, an outstanding deadline beyond the horizon is not yet a failure,
and a missing cover witness means only "not reached within this horizon".
These state covers do not establish an ordered request-to-completion sequence;
transaction-sequence cover syntax remains a future design question.

As a sanity experiment, adding an assumption `always: request == 0` makes
`can_accept` unreachable and lets `completes_in_time` pass vacuously. An
unreachable cover must be investigated: it may reveal restrictive assumptions
or an unreachable DUT state. Contradictory assumptions such as simultaneously
requiring `request == 0` and `request == 1` admit no execution at all; a property
PASS in that environment is not evidence of controller correctness.

## Proposed phases

1. **Semantic baseline and flow stabilization.** Consolidate precise property
   semantics, stabilize SVA/monitor equivalence on supported subsets, retain the
   raw-SVA escape hatch and define the external-lowering handoff for both
   generated and raw SVA. Build on the
   existing BMC + PDR flow rather than treating those tasks as new features.
2. **Environment contracts.** Specify and add structured assumptions, preserve
   the assert/assume/cover distinction in lowering, validate assumption ownership,
   and define simulation legality checking/stimulus-generation integration.
   Add bounded-change constraints with widened arithmetic, default trigger sanity
   covers and optional successful-response diagnostics alongside explicit
   scenarios. Define reset policies, including obligations active during reset
   and validity of previous-sample history.
3. **Measurement and differential validation.** Benchmark PDR, k-induction and
   SMT engines on representative controllers; improve counterexample/source
   mapping beyond existing replay. Compare native monitors with TENNCell-generated
   SVA processed by the external lowering tool on their supported overlap, using
   small exhaustive/formal equivalence tests or representative trace regressions.
   The external tool can serve as a reference/oracle without becoming a mandatory
   dependency for normal structured properties.
4. **Optional extensions.** Add richer plant/environment models and advanced or
   unbounded liveness only when justified by real use cases.

## Semantics to consolidate and questions to resolve

Existing contracts already specify independent overlapping trigger obligations,
inclusive bounds, offset-zero behavior, vacuous responses with no triggers, and
strict/weak finite-trace endings. Preserve these rules and explicitly validate
them across SVA and monitors, including multiple outstanding obligations and a
consequent occurring before its valid response window (which does not discharge
that obligation). Keep finite-trace endings distinct from formal horizons.

Still to specify: reset during an active obligation (cancel, restart or preserve),
reset reassertion and sampling policies, assumption syntax and detailed ownership
validation rules, fixed-point delta quantization/widths and history validity,
bounded persistence syntax, external-lowering integration and supported subsets,
simulation stimulus integration, and assumption diagnostic reporting/budgets.
New semantic choices must be documented precisely and match between SVA and
native monitors before rollout.
