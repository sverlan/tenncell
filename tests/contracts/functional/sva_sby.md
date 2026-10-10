# SVA SymbiYosys Contract (opt-in)

Runs only when `NNC_SBY` points to the `sby` executable of an oss-cad-suite
(yosys with the slang plugin and the yices solver next to it).

Each case generates `--sva-mode formal` output keeping one property of a
fixture under `tests/fixtures/verification/sva/formal/` and runs one task.

- `counter.yaml` (x = row): a true property passes `bmc`; a violation at row
  `r` fails `bmc` with `--sva-depth r + 1` and passes with `--sva-depth r`
  (rows 0, 1, 5; a bounded `eventually` that ignores a match before its
  window; a response that ignores satisfaction before age `a`; a response
  checked at age `n`; `then_always` from age `n` of the first trigger).
- `cover` respects `from_step`: reached exactly when its row is explored,
  never reached when the condition only holds before `from_step`.
- `follow.yaml` (free input, `environment` range): properties that need the
  row-aligned input copy and the range assumption hold for 12 rows; a
  property violated by an allowed input value fails.
- Proofs, `toggle.yaml` (x toggles, every property true for any run length):
  each kind keeping history (step counter, pending bits, `then_always` age)
  is proved by `prove_kind` and `prove_pdr`; a 20-row window gives UNKNOWN
  (never PASS) with k-induction length 4, PASS with 24, and PASS with PDR.
- False properties of `counter.yaml` (a violation at row 5, and one only
  after row 100) fail `prove_pdr` and are never PASS with `prove_kind`.

- `liveness.yaml` (with the `$live` helper): `bmc`, `prove_kind` and
  `prove_pdr` pass a true safety property next to a false liveness property
  (not their concern) and fail a false safety property; `cover` reaches its
  cover.

## Liveness (`test_sva_live.py`)

Runs only when `NNC_SBY_LIVE` is a command running an `sby` with the
`suprove` engine (Linux oss-cad-suite; on Windows for example
`wsl -e /mnt/c/tools/oss-cad-suite-linux/bin/sby`), started in the output
directory. Each case runs the `live` task on `liveness.yaml` (x toggles,
free input `u` in `[0, 5]`), keeping the listed properties:

- `eventually x == 1`, and `eventually x == 0` from row 5, pass;
- `eventually x == 2` fails, and so does `eventually u == 5` (the inputs may
  avoid 5 forever);
- `eventually x == 2` together with the false safety property
  `never x == 1` fails: the live task does not assume the other assertions;
- `eventually x == 1` together with `eventually x == 2` fails: the task's
  single status requires every liveness property.
