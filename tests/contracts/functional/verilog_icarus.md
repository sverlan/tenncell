# Verilog Icarus Contract (opt-in)

Runs only when `NNC_IVERILOG` points to the `iverilog` executable (with `vvp`
in the same directory, e.g. `C:/tools/oss-cad-suite/bin/iverilog.exe`);
otherwise the tests are skipped.

- Generate the RTL closure of a fixture under
  `tests/fixtures/transformers/verilog/input/` with `VerilogTransformer`, as
  `nnc-gen -t verilog` does.
- Compile it with the matching testbench from
  `tests/fixtures/transformers/verilog/sim/` (`iverilog -g2012`) and run it
  with `vvp -n`.
- The testbench prints `RESULT PASS` when the generated logic behaves as the
  TENNCell model does:
  - `negative_literals.yaml`: negative constants compile, and `y < -1` holds
    for `y = -1.5` after one step.
