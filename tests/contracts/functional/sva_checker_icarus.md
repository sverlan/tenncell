# SVA Checker Icarus Contract (opt-in)

Runs only when `NNC_IVERILOG` points to the `iverilog` executable.

- Every checked-in Verilog golden compiles as SystemVerilog. Missing external
  module definitions are ignored for this syntax check.
- Compile matrix: for every SVA fixture model (`controller.yaml`,
  `checker_interface/root.yaml`, `import_closure/parent.yaml`,
  `external/root.yaml`, `monitors/monitors.yaml`, `monitors/weak.yaml`), the
  generated RTL closure, checker and copied external sources compile together
  with `iverilog -g2012`, both without and with `FORMAL` defined. The external
  module of `external/root.yaml` is a stub passed as an SVA source.
- Together the models cover renamed inputs, imported inputs and outputs,
  aliases, FSM constants, raw SVA code, input-copy registers, the
  simulation-only row counter, every monitored property kind and weak
  semantics.
- The bind file is not compiled: Icarus does not support `bind`. It is checked
  by the Verilator contract (`sva_verilator.md`).
