"""CLI contract tests for `nnc-verify`."""

import json
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

from nnc.cli_verify import main

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "verification" / "cli"
COUNTER = FIXTURES / "counter.yaml"
TICKER = FIXTURES / "ticker.yaml"


def _run(*args: str) -> tuple[int, str, str]:
    with patch("sys.argv", ["nnc-verify", *args]):
        with patch("sys.stdout", new_callable=StringIO) as out:
            with patch("sys.stderr", new_callable=StringIO) as err:
                code = main()
    return code, out.getvalue(), err.getvalue()


def _json(*args: str) -> dict[str, dict]:
    code, out, err = _run(*args, "--json")
    assert err == "" or "Warning" in err, err
    return {item["id"]: item for item in json.loads(out)} | {"__exit__": code}


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


# --- simulation ---------------------------------------------------------------


def test_steps_simulates_n_plus_one_rows(tmp_path):
    # x equals the row number, so `always: x <= 5` passes on rows 0..5 only.
    assert _json(str(TICKER), "--steps", "5")["at_most_five"]["status"] == "pass"
    result = _json(str(TICKER), "--steps", "6")

    assert result["at_most_five"]["status"] == "fail"
    assert result["at_most_five"]["reported_row"] == 6
    assert result["__exit__"] == 1


def test_inputs_records_drive_rows_one_to_n(tmp_path):
    inputs = _write(tmp_path, "in.csv", "t\n1\n0\n1\n1\n0\n")

    results = _json(str(COUNTER), "--inputs", str(inputs))

    # `done` is internal (not an output); simulation records it anyway.
    assert results["reaches_done"]["status"] == "pass"
    assert results["counts_on_trigger"]["status"] == "pass"
    assert results["mc2_only"]["status"] == "skipped"
    assert results["__exit__"] == 0


def test_inputs_with_too_few_records_leave_eventually_open(tmp_path):
    inputs = _write(tmp_path, "in.csv", "t\n1\n")

    results = _json(str(COUNTER), "--inputs", str(inputs))

    # Rows 0..1 only: done never latches; strict (default) fails at the last row.
    assert results["reaches_done"]["status"] == "fail"
    assert results["reaches_done"]["reported_row"] == 1


@pytest.mark.parametrize(
    ("model", "args", "message"),
    [
        (COUNTER, ["--steps", "3"], "--steps is for models without inputs"),
        (TICKER, ["--inputs", "IN"], "--inputs is for models with inputs"),
        (COUNTER, ["--inputs", "BAD"], "unknown input columns: u"),
        (COUNTER, ["--steps", "-1"], "--steps must be a non-negative integer"),
    ],
)
def test_simulation_errors(tmp_path, model, args, message):
    inputs = _write(tmp_path, "in.csv", "t\n1\n")
    bad = _write(tmp_path, "bad.csv", "u\n1\n")
    args = [{"IN": str(inputs), "BAD": str(bad)}.get(a, a) for a in args]

    code, _, err = _run(str(model), *args)

    assert code == 1
    assert message in err


# --- recorded traces ----------------------------------------------------------


def test_trace_with_step_column_and_whitespace_delimiter(tmp_path):
    trace = _write(
        tmp_path,
        "trace.txt",
        "_step  t   x  done   note\n0  0  0  0  a\n10  1  1  0  b\n20  1  2  1  c\n",
    )

    results = _json(str(COUNTER), "--trace", str(trace), "--delimiter", " ")

    assert results["reaches_done"]["status"] == "pass"
    # The unused, non-numeric `note` column is ignored.
    assert results["__exit__"] == 0


def test_trace_failure_reports_row_and_step_label(tmp_path):
    trace = _write(tmp_path, "trace.csv", "step,t,x,done\n0,0,0,0\n5,1,0,0\n9,0,1,1\n")

    code, out, err = _run(str(COUNTER), "--trace", str(trace))

    assert code == 1
    assert "counts_on_trigger" in out and "row 1 (5)" in out
    assert "step labels jump from 0 to 5" in err


def test_trace_without_step_column_uses_first_step(tmp_path):
    trace = _write(tmp_path, "trace.csv", "t,x,done\n0,0,0\n0,-1,0\n")

    results = _json(str(COUNTER), "--trace", str(trace), "--first-step", "100")

    assert results["x_nonnegative"]["reported_label"] == 101


def test_later_step_named_column_is_data(tmp_path):
    trace = _write(tmp_path, "trace.csv", "t,x,done,time\n0,0,1,0\n0,0,1,0\n")

    results = _json(str(COUNTER), "--trace", str(trace), "--first-step", "7")

    # `time` is not first, so labels come from --first-step.
    assert results["x_nonnegative"]["status"] == "pass"


def test_column_used_only_by_skipped_property_may_be_missing(tmp_path):
    # `spare` is used only by mc2_only (targets mc2) and is absent from the trace.
    trace = _write(tmp_path, "trace.csv", "step,t,x,done\n0,0,0,1\n")

    assert _json(str(COUNTER), "--trace", str(trace))["__exit__"] == 0


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", "trace file is empty"),
        ("step,t,x,done\n", "trace has a header but no data rows"),
        ("step,t,x,x,done\n0,0,0,0,0\n", "duplicate column names: x"),
        ("step,t,x,done\n0,0,0\n", "trace.csv:2: expected 4 fields, found 3"),
        (
            "step,t,x,done\n0,0,abc,0\n",
            "trace.csv:2: value in column 'x' is not a number",
        ),
        ("step,t,x,done\n0,0,,0\n", "trace.csv:2: value in column 'x' is not a number"),
        ("step,t,x,done\nzero,0,0,0\n", "trace.csv:2: step label is not a number"),
        ("step,t,x,done\n1,0,0,0\n1,0,0,0\n", "strictly increasing"),
        ("step,t,x,done\nnan,0,0,0\n", "not finite"),
        ("step,t,done\n0,0,0\n", "trace has no column 'x'"),
        ("step,t,x,done\n0,0,inf,0\n", "column 'x' is not finite at row 0"),
    ],
)
def test_trace_errors(tmp_path, text, message):
    trace = _write(tmp_path, "trace.csv", text)

    code, _, err = _run(str(COUNTER), "--trace", str(trace))

    assert code == 1
    assert message in err


def test_evaluation_error_is_an_operational_error(tmp_path):
    model = _write(
        tmp_path,
        "model.yaml",
        "cells:\n  - id: 1\n    contents:\n      - x = 0\n    output: [x]\n"
        "rules:\n  - x - 1 -> x\n"
        "verification:\n  properties:\n    - id: root\n      always: sqrt(x) >= 0\n",
    )

    code, _, err = _run(str(model), "--steps", "2")

    assert code == 1
    assert (
        "Property 'root': evaluating the 'always' condition at row 1 (label 1)" in err
    )


def test_model_without_properties_is_an_error(tmp_path):
    model = _write(
        tmp_path,
        "model.yaml",
        "cells:\n  - id: 1\n    contents:\n      - x = 0\n    output: [x]\n"
        "rules:\n  - x + 1 -> x\n",
    )

    code, _, err = _run(str(model), "--steps", "1")

    assert code == 1
    assert "No generic verification properties found" in err


def test_pending_does_not_fail(tmp_path):
    model = _write(
        tmp_path,
        "model.yaml",
        "cells:\n  - id: 1\n    contents:\n      - x = 0\n    output: [x]\n"
        "rules:\n  - x + 1 -> x\n"
        "verification:\n  trace_semantics: weak\n  properties:\n"
        "    - id: big\n      eventually: x > 100\n",
    )

    code, out, _ = _run(str(model), "--steps", "2")

    assert code == 0
    assert "pending" in out and "end of trace" in out


# --- imports ------------------------------------------------------------------

COMPOSED = FIXTURES / "composed.yaml"
REFERENCES = FIXTURES.parent / "references"


@pytest.mark.parametrize("option", ["--import-path", "--import-paths"])
def test_imported_outputs_are_simulated_as_alias_port(tmp_path, option):
    inputs = _write(tmp_path, "in.csv", "sample\n1\n2\n3\n")

    results = _json(str(COMPOSED), "--inputs", str(inputs), option, str(REFERENCES))

    assert results["level_nonnegative"]["status"] == "pass"
    assert results["level_rises"]["status"] == "pass"


def test_trace_uses_alias_port_columns_for_imports(tmp_path):
    trace = _write(tmp_path, "trace.csv", "step,sample,sensor0__level\n0,0,0\n1,1,-1\n")

    results = _json(
        str(COMPOSED), "--trace", str(trace), "--import-path", str(REFERENCES)
    )

    assert results["level_nonnegative"]["status"] == "fail"
    assert results["level_nonnegative"]["reported_row"] == 1


def test_missing_import_is_an_error(tmp_path):
    inputs = _write(tmp_path, "in.csv", "sample\n1\n")

    code, _, err = _run(str(COMPOSED), "--inputs", str(inputs))

    assert code == 1
    assert "sensor.yaml" in err


# --- trace format details -----------------------------------------------------


def test_first_label_column_is_also_data(tmp_path):
    model = _write(
        tmp_path,
        "model.yaml",
        "cells:\n  - id: 1\n    contents:\n      - time = 0\n    output: [time]\n"
        "rules:\n  - time + 1 -> time\n"
        "verification:\n  properties:\n    - id: early\n      always: time < 20\n",
    )
    trace = _write(tmp_path, "trace.csv", "time\n0\n10\n20\n")

    results = _json(str(model), "--trace", str(trace))

    assert results["early"]["status"] == "fail"
    assert results["early"]["reported_row"] == 2
    assert results["early"]["reported_label"] == 20


def test_integral_float_labels_are_reported_as_integers(tmp_path):
    trace = _write(tmp_path, "trace.csv", "step,t,x,done\n0.0,0,0,0\n1.0,0,-1,0\n")

    results = _json(str(COUNTER), "--trace", str(trace))

    label = results["x_nonnegative"]["reported_label"]
    assert label == 1 and isinstance(label, int)


def test_float_labels_are_kept(tmp_path):
    trace = _write(tmp_path, "trace.csv", "time,t,x,done\n0.0,0,0,0\n0.5,0,-1,0\n")

    code, _, err = _run(str(COUNTER), "--trace", str(trace), "--json")

    assert code == 1
    assert "Warning" not in err  # no gap warning for non-integral labels


def test_quoted_csv_fields(tmp_path):
    trace = _write(
        tmp_path, "trace.csv", 'step,t,x,done,note\n0,0,0,1,"a, b"\n1,"0","1",1,c\n'
    )

    assert _json(str(COUNTER), "--trace", str(trace))["__exit__"] == 0


def test_blank_lines_are_skipped(tmp_path):
    trace = _write(tmp_path, "trace.csv", "step,t,x,done\n\n0,0,0,1\n   \n1,0,1,1\n")

    assert _json(str(COUNTER), "--trace", str(trace))["__exit__"] == 0


@pytest.mark.parametrize(
    ("labels", "warned"),
    [
        (["0", "1", "2"], False),
        (["0", "2", "3"], True),
        (["0.0", "1.0", "3.0"], True),
        (["0", "0.5", "1"], False),
    ],
)
def test_gap_warning(tmp_path, labels, warned):
    rows = "".join(f"{label},0,0,1\n" for label in labels)
    trace = _write(tmp_path, "trace.csv", "step,t,x,done\n" + rows)

    _, _, err = _run(str(COUNTER), "--trace", str(trace))

    assert ("step labels jump" in err) == warned


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("step,t,,x,done\n0,0,0,0,0\n", "trace.csv:1: column 3 has an empty name"),
        ("step,t,x,done\n,,,\n", "trace.csv:2: step label is not a number"),
        ("step,t,x,done\n0,0,\x00,0\n", "trace.csv:2"),
    ],
)
def test_more_trace_errors(tmp_path, text, message):
    trace = _write(tmp_path, "trace.csv", text)

    code, _, err = _run(str(COUNTER), "--trace", str(trace))

    assert code == 1
    assert message in err


# --- input files --------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", "input file is empty"),
        ("t,t\n1,1\n", "in.csv:1: duplicate input columns: t"),
        ("t,\n1,1\n", "in.csv:1: column 2 has an empty name"),
        ("t,u\n1,1\n", "unknown input columns: u"),
        ("t\n1,2\n", "in.csv:2: expected 1 fields, found 2"),
        ("t\nabc\n", "in.csv:2: value in column 't' is not a number"),
    ],
)
def test_input_file_errors(tmp_path, text, message):
    inputs = _write(tmp_path, "in.csv", text)

    code, _, err = _run(str(COUNTER), "--inputs", str(inputs))

    assert code == 1
    assert message in err


def test_missing_input_column(tmp_path):
    model = _write(
        tmp_path,
        "model.yaml",
        "cells:\n  - id: 1\n    contents:\n      - a = 0\n      - b = 0\n"
        "    input: [a, b]\n"
        "verification:\n  properties:\n    - id: ok\n      always: a >= 0\n",
    )
    inputs = _write(tmp_path, "in.csv", "a\n1\n")

    code, _, err = _run(str(model), "--inputs", str(inputs))

    assert code == 1
    assert "missing input columns: b" in err


# --- usage -------------------------------------------------------------------


@pytest.mark.parametrize(
    "args",
    [
        [str(TICKER)],
        [str(TICKER), "--steps", "1", "--trace", "x.csv"],
        [str(TICKER), "--steps", "many"],
        [str(TICKER), "--steps", "1", "--delimiter", ";;"],
        [str(TICKER), "--steps", "1", "--delimiter", ""],
    ],
)
def test_usage_errors_exit_with_two(args):
    with patch("sys.argv", ["nnc-verify", *args]):
        with patch("sys.stderr", new_callable=StringIO):
            with pytest.raises(SystemExit) as error:
                main()

    assert error.value.code == 2


def test_json_shape(tmp_path):
    code, out, _ = _run(str(TICKER), "--steps", "2", "--json")

    assert code == 0
    assert json.loads(out) == [
        {
            "id": "at_most_five",
            "kind": "always",
            "status": "pass",
            "trigger_row": None,
            "trigger_label": None,
            "reported_row": None,
            "reported_label": None,
            "open_obligations": [],
        },
        {
            "id": "covers_three",
            "kind": "cover",
            "status": "not_covered",
            "trigger_row": None,
            "trigger_label": None,
            "reported_row": None,
            "reported_label": None,
            "open_obligations": [],
        },
    ]
