# MC2 Tool Contract (opt-in)

Runs only when `NNC_MC2_JAR` points to `MC2v2.0beta2.jar` and `java` is on `PATH`;
otherwise the test is skipped.

- Generate MC2 files with `nnc-gen -t mc2` from `tests/fixtures/verification/mc2_tool/fsm_counter.yaml`.
- Simulate the same model with `nnc-sim --csv-include-step --csv-include-initial` on `start.csv`, once `;`-separated and once space-separated.
- Run `java -jar MC2v2.0beta2.jar stoch <trace> <queries>` (with `-snoopy` for the `;` trace).
- MC2 accepts both traces and prints `1.0,true,true,1.0,0.0` for the queries in `.mc2.ids` order, including a query that uses the NOT sign (U+00AC).
