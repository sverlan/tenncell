# SVA Verilator Lint Contract (opt-in)

Runs only when `NNC_VERILATOR` points to the `verilator_bin` executable.
`VERILATOR_ROOT` defaults to `<bin>/../share/verilator` (oss-cad-suite layout).

- For every SVA fixture model of the Icarus compile matrix, the output of mode
  `both` (RTL closure, checker, bind file, copied external sources) passes
  `verilator_bin --lint-only` with the default warnings, the root module as top.
  The bind file is elaborated: a wrong connection in it fails the lint.
- With `-Wall`, the generated checker and bind files raise no warning except
  `DECLFILENAME` (the file `<stem>_sva.sv` holds the module `<module>_sva` by
  design). Warnings in the RTL itself are outside this contract.
