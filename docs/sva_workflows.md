# SVA Verification Workflows

This tutorial takes two small models through RTL monitor simulation, bounded
model checking, cover, proofs, liveness, and self-checking witness replay. For
property syntax and backend semantics, see `docs/generic_properties.md`. The
exact implementation contract is in `rules.md`, section "SVA Backend".

TENNCell generates files but does not run external tools. The commands below
assume `nnc-gen`, `nnc-verify`, `iverilog`, `vvp`, and `sby` are on `PATH`.
Formal tasks require Yosys with the slang plugin and a solver. The `live` task
also requires `suprove`; Linux oss-cad-suite includes it. Run commands from the
repository root unless a step explicitly changes directory.

## 1. What the tasks answer

| Task | Question | Successful result |
|---|---|---|
| RTL simulation | What happened on this finite stimulus? | `SVA_RESULT ... pass` or `covered` |
| `bmc` | Is there a failure in rows `0..D-1`? | `PASS`: none was found within depth `D` |
| `cover` | Can each cover objective be reached within depth `D`? | `PASS`: a witness was found |
| `prove_kind` | Can k-induction prove every safety assertion? | `PASS`; `UNKNOWN` is not a proof |
| `prove_pdr` | Can PDR prove every safety assertion? | `PASS` |
| `live` | Does every unbounded `eventually` hold on every infinite run? | `PASS` |

`--sva-depth D` sets the BMC/cover horizon and the k-induction length in
property rows: BMC and cover explore property rows `0..D-1`. The generated
`.sby` uses engine depth `D + 2` (one step for the reset and one because a
clocked assertion reports a row one step later); the `live` task has no depth.
PDR and successful k-induction prove
safety for runs of any length. If k-induction returns `UNKNOWN`, increase the
depth or try PDR. Anything other than `PASS` is not a proof.

All safety assertions are checked together. Likewise, all unbounded
`eventually` properties share one `live` status; a liveness failure does not
name the individual property. When diagnosing an aggregate result, temporarily
retain or target one property at a time.

## 2. Passing monitor simulation

`examples/verification/sva_flag.yaml` is autonomous: `x` changes from 0 to 1
and then remains set. First check the floating-point model:

```text
nnc-verify examples/verification/sva_flag.yaml --steps 6
```

It reports six `pass` results and one `covered` result. Generate the equivalent
RTL run and simulate it:

```text
nnc-gen examples/verification/sva_flag.yaml -t sva --sva-steps 6 -o out/flag
cd out/flag
iverilog -g2012 -o sim.vvp sva_flag.sv sva_flag_sva.sv sva_flag_tb.sv
vvp sim.vvp
cd ../..
```

Icarus may print `sva_flag.sv:20: warning: always_comb process has no
sensitivities.` It is harmless: the rule `1 -> x` reads only constants, so the
combinational block has nothing to react to, and `always_comb` still runs once
at time 0, which is all a constant needs.

The RTL prints the same seven statuses as `SVA_RESULT` lines. A failed
assertion makes the testbench exit nonzero. The RTL uses fixed-point arithmetic,
so exact agreement with native is expected only when the values and operations
are represented exactly.

For a model with inputs, use `--sva-inputs inputs.csv` instead of
`--sva-steps`. Compare native with the generated quantized inputs:

```text
nnc-verify model.yaml --inputs out/model_inputs_decoded.csv
```

## 3. BMC, cover and proofs

Generate formal files for four property rows:

```text
nnc-gen examples/verification/sva_flag.yaml -t sva --sva-mode formal --sva-depth 4 -o out/flag-formal
cd out/flag-formal
sby -f sva_flag.sby bmc
sby -f sva_flag.sby cover
sby -f sva_flag.sby prove_kind
sby -f sva_flag.sby prove_pdr
```

All four tasks end in `PASS`. Here their meanings differ:

- BMC found no failure in rows 0 through 3. It did not prove later rows.
- Cover reached `covers_one` and wrote
  `sva_flag_cover/engine_0/trace0.yw`. Cover witnesses use numbered
  `traceN.yw` names.
- K-induction and PDR proved all safety assertions for arbitrary run lengths.

Run tasks by name. If a model also has a `live` task and `suprove` is absent,
running `sby -f sva_flag.sby` without a task runs everything and ends in an
error for `live`, even though the other tasks may pass.

To produce simulation and formal artifacts in one generation, provide both a
simulation source and a formal depth:

```text
cd ../..
nnc-gen examples/verification/sva_flag.yaml -t sva --sva-mode both --sva-steps 6 --sva-depth 4 -o out/flag-both
```

## 4. Liveness

The unbounded `eventually: x == 1` in `sva_flag.yaml` is checked only by the
`live` task. From the formal output directory:

```text
cd out/flag-formal
sby -f sva_flag.sby live
cd ../..
```

It ends in `PASS`: every infinite run eventually reaches `x == 1`. The task
uses `suprove`, has no finite depth, and produces no replay trace. Safety tasks
ignore the liveness cell; the live task removes safety assertions rather than
turning them into assumptions.

## 5. A failing BMC check

`examples/verification/sva_failure.yaml` has an input `u` constrained to
`0..2`, copies it to `x`, and deliberately asserts `x <= 1`. Generate and run
BMC:

```text
nnc-gen examples/verification/sva_failure.yaml -t sva --sva-mode formal --sva-depth 3 -o out/failure-formal
cd out/failure-formal
sby -f sva_failure.sby bmc
cd ../..
```

BMC ends in `FAIL`, reports `sva_x_is_at_most_one_check`, and writes the
counterexample to:

```text
out/failure-formal/sva_failure_bmc/engine_0/trace.yw
```

That `FAIL` is a useful result: a concrete allowed RTL execution violates the
assertion.

## 6. Replaying the BMC counterexample

Generate a simulation from the witness:

```text
nnc-gen examples/verification/sva_failure.yaml -t sva --sva-replay out/failure-formal/sva_failure_bmc/engine_0/trace.yw -o out/failure-replay
cd out/failure-replay
iverilog -g2012 -o replay.vvp sva_failure.sv sva_failure_sva.sv sva_failure_tb.sv
vvp replay.vvp
cd ../..
```

The expected output includes:

```text
SVA_REPLAY reproduced on row 1
```

For replay, a zero exit status means the expected failure was reproduced; it
does not mean the property passed. `SVA_REPLAY NOT reproduced` is an error.

The replay directory also contains `sva_failure_inputs_decoded.csv`. Check the
same quantized inputs in the floating-point model:

```text
nnc-verify examples/verification/sva_failure.yaml --inputs out/failure-replay/sva_failure_inputs_decoded.csv
```

This example fails natively on row 1 too. A native/RTL disagreement can still
be a legitimate fixed-point rounding or overflow difference; it does not make
the RTL witness replay invalid.

## 7. Replaying a cover witness

Cover replay uses the numbered witness produced in section 3:

```text
nnc-gen examples/verification/sva_flag.yaml -t sva --sva-replay out/flag-formal/sva_flag_cover/engine_0/trace0.yw -o out/flag-cover-replay
cd out/flag-cover-replay
iverilog -g2012 -o replay.vvp sva_flag.sv sva_flag_sva.sv sva_flag_tb.sv
vvp replay.vvp
cd ../..
```

The expected output is `SVA_REPLAY reproduced on row 1`. For a cover witness,
this means the cover was first hit on the expected row. The flag model is
autonomous, so compare the same number of rows with:

```text
nnc-verify examples/verification/sva_flag.yaml --steps 1
```

## 8. Replay limits

- Replay accepts BMC and cover Yosys witnesses. K-induction and PDR traces are
  not supported, and liveness produces no trace.
- The witness is structurally matched by port names and widths, not
  authenticated as belonging to the model. A wrong compatible witness is
  accepted at generation time but the self-checking simulation should report
  `NOT reproduced`.
- Solver bits left unknown are replayed as zero.
- `nnc-gen` generates the replay; it never invokes Icarus, Verilator,
  SymbiYosys, or `nnc-verify` itself.
