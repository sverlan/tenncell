# SVA slang Contract (opt-in)

Runs only when `NNC_YOSYS` points to a `yosys` executable with the yosys-slang
plugin (`-m slang`, shipped with the oss-cad-suite).

- `read_slang --ast-compilation-only` (full parsing and elaboration, no
  synthesis) rejects an invalid SVA control file, so the check is meaningful.
- For every SVA fixture model, the generated files compile: monitor style in
  mode `both` (checker and bind file, also with `FORMAL` defined, as
  SymbiYosys reads it), and simulation in monitor and concurrent
  style (checker and testbench). The concurrent style is skipped for the
  weak-semantics model, which it rejects.
