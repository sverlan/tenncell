# MC2 / Native Cross-check Contract (opt-in)

Runs only when `NNC_MC2_JAR` points to `MC2v2.0beta2.jar` and `java` is on `PATH`;
otherwise the test is skipped.

- `tests/fixtures/verification/mc2_crosscheck/model.yaml` defines every generic property kind on a condition `p` and a trigger `t`, with `from_step`, `after`, and `within` variants.
- Each trace in `traces/` covers a case: shorter than `from_step`, overlapping triggers, a trigger on the last row, windows cut by the end of the trace, persistence end cases, `p` always true, and `p` never true.
- For `trace_semantics` `strict` and `weak`, the properties are translated with `render_mc2`, run with `java -jar MC2v2.0beta2.jar stoch <trace> <queries> -quiet`, and checked with the native checker on the same trace.
- For every property MC2 gives `1` for native `pass` and `covered`, `0` for `fail` and `not_covered`, and, for weak `pending`, `1` except for unbounded `eventually`, which gives `0` (compared with a tolerance of `1e-9`).
