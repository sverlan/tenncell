# Agents Guide

## Working Philosophy

- Treat the public API, internal helpers, and functional examples as separate contract layers.
- Prefer small, validated, reviewable changes over broad refactors.
- Keep `ideas.md` untouched unless the user explicitly asks to edit it.
- Do not use `src/examples/` as the source of truth for tests; examples live under `examples/` and tests own their own fixtures.

## Contract Rules

- Public API behavior must be documented with docstrings and parameter/return/raise specs.
- Internal helpers should have short factual docstrings; full public-style docs are not required.
- Unit tests must correspond to written contracts, not implementation details.
- Functional tests must correspond to scenario contracts and use dedicated fixtures under `tests/fixtures/`.
- Minimize generated YAML inside tests; prefer checked-in fixture files for scenario contracts and inline YAML only for small focused unit cases.
- CLI tests should stay separate from unit and functional tests.
- Coverage-only tests belong in `tests/coverage_tests/` and should not be mixed with contract tests.

## Examples

- Keep simple standalone examples at the top level of `examples/`.
- Put more complex examples in subfolders by concern.
- Put multi-file examples in dedicated folders so each example is self-contained.
- Keep FPGA and backend-specific examples under `examples/fpga/`, with subfolders for grouped examples.
- For standalone examples, use YAML comments or `module.description` for human-readable context.
- For test-owned examples, keep the written contract in `tests/contracts/functional/`.

## Validation

- Before a commit, run `pdm run lint`, `pdm run typecheck`, and `pdm test`.
- Run `pdm run format` only on major slices, version bumps, or when the user explicitly asks for a formatting pass.
- Run `pdm test` after each meaningful slice.
- Validate changed examples directly with the relevant loader/transformer path.
- For YAML example changes, ensure every example under `examples/` still loads or transforms successfully.
- If a change affects behavior, schema, or code generation, update `rules.md`.

## Tooling Scope

- Keep `pdm run lint`, `pdm run format`, and `pdm run typecheck` focused on source code and contract tests.
- Do not reformat or typecheck golden fixture files under `tests/fixtures/` unless the user explicitly asks for that.
- Do not let formatting churn rewrite generated contract fixtures just because they are valid Python or YAML.
- When in doubt about formatting, ask before touching golden files.

## Commit Policy

- Commit each coherent slice separately.
- Do not mix example moves, contract changes, documentation updates, and behavior fixes in one commit unless they are tightly coupled.
- Commit after validation, not before.
- Leave unrelated user changes alone.
- Ask for formatting before committing only on major slices or version bumps, unless the user explicitly requests it.

## Pre-release checklist

Before each version release:

1. Run the full test suite and ensure it passes (`pdm test`).
2. Update `CHANGELOG.md` with the release notes for the new version.

## Change documentation

For each change in logic, behavior, schema, or code generation:

1. Update `rules.md` to document the change.

