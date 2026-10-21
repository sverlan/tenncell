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



# Agent Instructions

If `AGENT_PROTOCOL.md` exists in the repository root, read and follow it before beginning work.

`AGENT_PROTOCOL.md` contains local agent-to-agent collaboration rules and may not be present in every checkout.

If the file does not exist, continue normally without it.

Unless `AGENT_PROTOCOL.md` says otherwise, follow the repository's normal instructions and the user's explicit requests.

## Subagent model selection

- Whenever possible, delegate bounded, low-risk tasks to subagents and explicitly choose a cheaper model when it is adequate; do not default to running another copy of the primary model for routine work.
- Good candidates include running test, lint, type-check or coverage commands; summarizing long command output so it does not consume the primary agent's context; listing changed files or repository facts; checking documentation links and status tables; locating definitions and callers; and performing narrow, mechanical consistency checks.
- Use another copy of the primary model only when the delegated task itself needs comparable reasoning depth, such as an independent review of subtle temporal semantics or a genuinely complex parallel investigation.
- Keep architecture decisions, subtle SVA semantic analysis, final review judgments and risky repository changes with a model capable of handling their full complexity.
- Give each subagent a narrow task and request a concise result containing the command outcome, failures and material evidence rather than the complete raw log.
- The primary agent remains responsible for checking the subagent's conclusions and for the final result. Delegation does not relax any validation, safety, role or review requirement in this guide or `AGENT_PROTOCOL.md`.
