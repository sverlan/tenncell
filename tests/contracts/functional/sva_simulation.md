# SVA Simulation Contract (opt-in)

Runs in Icarus when `NNC_IVERILOG` points to the `iverilog` executable (`vvp`
in the same directory). The Verilator cases run when `NNC_VERILATOR` points to
`verilator_bin` and `make` and `g++` are on `PATH` (or in `NNC_CXX_PATH`).

Every run uses the generated testbench `<stem>_tb.sv` and stimulus, and is
compared, line for line (statuses, trigger rows, reported rows, open
obligations), with `native` on the decoded inputs (`<stem>_inputs_decoded.csv`)
or the same number of steps; the simulation exits with an error exactly when a
property fails.

- Fixture: `tests/fixtures/verification/sva/monitors/monitors.yaml` with every
  property kind (`always`, `never`, `eventually`, `eventually within`, `cover`,
  `when`/`then` `after` and `within`, `when`/`then_always`), with and without
  `from_step`, passing, failing and still open at the end; zero bounds,
  overlapping obligations, satisfaction before the window start, a window that
  starts after the trigger; an input with a renamed port read through the
  checker's copy; a constant, an FSM state and a fixed-point product.
- `monitors.yaml` runs on the first 0 to 6 records of `inputs.csv` (0 records:
  row 0 only), so runs end before, inside and after the windows and pending
  obligations, for `strict` and `weak` semantics.
- `autonomous.yaml` (no inputs) runs 0, 1 and 20 steps; 20 steps go past the
  saturating step counter.
- `imported_input/parent.yaml` connects a child input to a changing parent
  register and checks that the imported input is the value given to the
  child during the transition, not the parent's live post-edge value; the SVA
  checker and `nnc-verify` agree (both properties pass).
- `imported_input/numbers.yaml` (numbers as connections) and `root_input.yaml`
  (a root input passed to a child: the child and the parent's rules both get
  the record of the step): the SVA checker and `nnc-verify` agree.
- `imported_input/twins.yaml` imports one module twice: the instances keep
  separate state, and the SVA checker and `nnc-verify` agree.
- `imported_input/chain.yaml` (an import reading another import's output, one
  row later) and `loop.yaml` (two imports reading each other): the SVA
  checker and `nnc-verify` agree.
- `shapes.yaml` runs the MC2 cross-check trace shapes
  (`verification/mc2_crosscheck/traces`, columns `p`, `t`) as input records.
- `divergence.yaml` documents expected differences: Q8.8 overflow and rounding
  make SVA fail where `native` passes.
- Verilator: three of these runs (inputs, steps, an overlapping-trigger shape)
  as `--binary` builds give the same lines.
- Concurrent style in Verilator: `concurrent_basic.yaml` (plain assertions and
  zero-bound responses, the forms Verilator 5 runs) reports `SVA_FAIL <id> row
  <row>` for exactly the properties `native` fails, the first row of each being
  `native`'s reported row.
- The RTL and checker also compile with `FORMAL` defined (no result recorder),
  without the bind file, which Icarus does not support.
