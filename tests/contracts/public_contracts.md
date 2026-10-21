# Public Contracts

This file lists the public API the project intends to support for library users.
These are the names that should be documented with full docstrings and parameter
descriptions, and that tests should treat as the current public contract.

## Core model

- `nnc.NncSystem`
- `nnc.Cell`
- `nnc.Rule`
- `nnc.model.NncSystem`
- `nnc.model.Cell`
- `nnc.model.Rule`
- `nnc.model.ImportConfig`
- `nnc.model.ModuleConfig`
- `nnc.model.ResolvedReference`

`Rule.source_location` is a physical `YamlLocation` (source path and 1-based
rule line), or `None` without YAML provenance. It remains attached when a rule
is moved to another system; it is not a path into that system's source index.

## Parser entry points

- `nnc.parser.parse_expression`
- `nnc.parser.parse_condition`
- `nnc.parser.parse_rule`
- `nnc.parser.parse_variable_assignment`

## Transformer entry points

- `nnc.transformers.BaseTransformer`
- `nnc.transformers.PythonTransformer`
- `nnc.transformers.VerilogTransformer` (including `observe(system)`, which
  returns a `VerilogObservation`; `VerilogObservation`, `ObservedSignal` and
  `ObservedSignalKind` are exported from `nnc.transformers.verilog`)
- `nnc.transformers.WebotsTransformer`
- `nnc.transformers.SvaTransformer` (`generate(system)` returns
  `nnc.transformers.sva_transformer.SvaOutput`; `write(output, out_dir)`),
  configured with `nnc.verification.sva.SvaOptions`; invalid options raise
  `nnc.verification.sva.SvaOptionsError`. The `-t sva` command line is not
  exposed yet.

`VerilogTransformer.transform` and `observe`, and the RTL generation within
`SvaTransformer.generate`, raise `YamlLocatedError` (a `ValueError`) for
unsupported rule expressions detected before emission. These errors identify
the producer or guard, display the effective rule, and include its original
physical YAML file and rule line when available. A rule without provenance
uses the system file, when known, without guessing a line. This guarantee does
not extend to encoding, reference, or conversion failures during emission.

## Verilog config model

- `nnc.transformers.verilog.VerilogHardwareConfig`
- `nnc.transformers.verilog.RealEncoding`
- `nnc.transformers.verilog.ClockConfig`
- `nnc.transformers.verilog.ResetConfig`
- `nnc.transformers.verilog.PortConfig`
- `nnc.transformers.verilog.ExternalModuleSchema`
- `nnc.transformers.verilog.ExternalInstance`

## Webots config model

- `nnc.transformers.webots.WebotsConfig`
- `nnc.transformers.webots.WebotsBindingConfig`

## CLI entry points

- `nnc.cli.main`
- `nnc.cli_transform.main`

## Contract rules

- Public names should have full docstrings with purpose, parameters, return
  values, and relevant exceptions.
- Public names may evolve during elaboration, but changes should be deliberate
  and reflected in the docs and tests.
- Internal helpers do not belong in this list unless they become part of the
  supported library surface.
