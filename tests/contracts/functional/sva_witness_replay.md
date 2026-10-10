# SVA Witness Replay Contract (opt-in)

Runs only when `NNC_SBY` and `NNC_IVERILOG` are set.

Each case keeps one property of a fixture, finds a witness with SymbiYosys,
replays it with `--sva-replay` in Icarus, and runs `native` on the decoded
inputs (or the same number of steps).

- bmc counterexamples (a free input reaching a forbidden value, a model
  without inputs, a response window): the self-checking testbench prints
  `SVA_REPLAY reproduced on row N` and exits 0, and `native` agrees line for
  line.
- A `cover` witness is replayed and covered in both.
- Fixed-point overflow (`monitors/divergence.yaml`): the replay reproduces the
  RTL failure on row 7 while `native` passes; the divergence is reported, it
  is not a replay failure.
- A witness with the right ports but of other checks (a checker keeping only
  a true property) is accepted and reported `SVA_REPLAY NOT reproduced`, with
  a failing exit status.
