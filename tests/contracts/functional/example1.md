# Example 1 Contract

- Load a minimal single-cell TENNCell system from YAML.
- Preserve the declared variable set and initial values.
- Support repeated stepping with the read-only input variable `u`; `x` is internal writable state.
- Produce the documented sequence of `x`, `y`, `E`, `z`, and `u` values.
