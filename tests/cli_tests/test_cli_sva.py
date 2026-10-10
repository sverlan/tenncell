"""CLI contract tests for `nnc-gen -t sva`."""

from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

from nnc.cli_transform import main

SVA = Path(__file__).resolve().parents[1] / "fixtures" / "verification" / "sva"
MONITORS = SVA / "monitors" / "monitors.yaml"
INPUTS = SVA / "monitors" / "inputs.csv"
AUTONOMOUS = SVA / "monitors" / "autonomous.yaml"


def _run(*args: str) -> tuple[int, str, str]:
    """Run nnc-gen; usage errors (argparse) give their exit code."""
    with patch("sys.argv", ["nnc-gen", *args]):
        with patch("sys.stdout", new_callable=StringIO) as out:
            with patch("sys.stderr", new_callable=StringIO) as err:
                try:
                    code = main()
                except SystemExit as exit_:
                    code = exit_.code
    return code, out.getvalue(), err.getvalue()


def test_inputs_give_rtl_checker_testbench_and_stimulus(tmp_path):
    code, _, err = _run(
        str(MONITORS), "-t", "sva", "--sva-inputs", str(INPUTS), "-o", str(tmp_path)
    )

    assert code == 0, err
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "monitors.sv",
        "monitors_inputs.hex",
        "monitors_inputs_decoded.csv",
        "monitors_sva.sv",
        "monitors_tb.sv",
    ]
    assert (tmp_path / "monitors_inputs_decoded.csv").read_text(encoding="utf-8") == (
        "u\n1.0\n2.0\n5.0\n0.0\n3.0\n0.0\n"
    )


def test_steps_give_a_testbench_without_stimulus_files(tmp_path):
    code, _, err = _run(
        str(AUTONOMOUS), "-t", "sva", "--sva-steps", "5", "-o", str(tmp_path)
    )

    assert code == 0, err
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "autonomous.sv",
        "autonomous_sva.sv",
        "autonomous_tb.sv",
    ]
    assert "localparam int RECORDS = 5;" in (tmp_path / "autonomous_tb.sv").read_text(
        encoding="utf-8"
    )


def test_inputs_options_are_passed_to_the_reader(tmp_path):
    inputs = tmp_path / "in.txt"
    inputs.write_text("preamble line\nu\n1\n2\n", encoding="utf-8")
    out = tmp_path / "out"

    code, _, err = _run(
        str(MONITORS),
        "-t",
        "sva",
        "--sva-inputs",
        str(inputs),
        "--delimiter",
        " ",
        "--skip-lines",
        "1",
        "-o",
        str(out),
    )

    assert code == 0, err
    assert (out / "monitors_inputs_decoded.csv").read_text(encoding="utf-8") == (
        "u\n1.0\n2.0\n"
    )


def test_concurrent_style_writes_assertions(tmp_path):
    code, _, err = _run(
        str(MONITORS),
        "-t",
        "sva",
        "--sva-style",
        "concurrent",
        "--sva-inputs",
        str(INPUTS),
        "-o",
        str(tmp_path),
    )

    assert code == 0, err
    assert "assert property" in (tmp_path / "monitors_sva.sv").read_text(
        encoding="utf-8"
    )


def test_concurrent_style_with_weak_semantics_is_an_error(tmp_path):
    code, _, err = _run(
        str(SVA / "monitors" / "weak.yaml"),
        "-t",
        "sva",
        "--sva-style",
        "concurrent",
        "--sva-steps",
        "1",
        "-o",
        str(tmp_path),
    )

    assert code == 1
    assert "concurrent SVA style does not support trace_semantics: weak" in err


def test_formal_mode_writes_the_sby_file_and_bind_without_testbench(tmp_path):
    code, _, err = _run(
        str(AUTONOMOUS),
        "-t",
        "sva",
        "--sva-mode",
        "formal",
        "--sva-depth",
        "7",
        "-o",
        str(tmp_path),
    )

    assert code == 0, err
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "autonomous.sby",
        "autonomous.sv",
        "autonomous_sva.sv",
        "autonomous_sva_bind.sv",
        "autonomous_sva_live.v",
    ]
    sby = (tmp_path / "autonomous.sby").read_text(encoding="utf-8")
    # 7 rows + the reset step + the clocked check; not for the live task.
    assert "~live: depth 9" in sby
    # Unbounded eventually is checked as liveness by the live task.
    assert "live: aiger suprove" in sby
    assert "reaches_thirty" not in err


def test_both_modes_write_testbench_and_formal_files(tmp_path):
    code, _, err = _run(
        str(AUTONOMOUS),
        "-t",
        "sva",
        "--sva-mode",
        "both",
        "--sva-steps",
        "3",
        "-o",
        str(tmp_path),
    )

    assert code == 0, err
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "autonomous.sby",
        "autonomous.sv",
        "autonomous_sva.sv",
        "autonomous_sva_bind.sv",
        "autonomous_sva_live.v",
        "autonomous_tb.sv",
    ]


def test_stimulus_in_formal_mode_is_an_error(tmp_path):
    code, _, err = _run(
        str(AUTONOMOUS),
        "-t",
        "sva",
        "--sva-mode",
        "formal",
        "--sva-steps",
        "3",
        "-o",
        str(tmp_path),
    )

    assert code == 1
    assert "--sva-inputs, --sva-steps and --sva-replay are for simulation" in err


def test_replay_writes_the_witness_stimulus(tmp_path):
    witness = SVA / "replay" / "follow_never_max.yw"

    code, _, err = _run(
        str(SVA / "formal" / "follow.yaml"),
        "-t",
        "sva",
        "--sva-replay",
        str(witness),
        "-o",
        str(tmp_path),
    )

    assert code == 0, err
    assert (tmp_path / "follow_inputs_decoded.csv").read_text(encoding="utf-8") == (
        "u\n5.0\n"
    )
    assert "replay of follow_never_max.yw" in (tmp_path / "follow_tb.sv").read_text(
        encoding="utf-8"
    )


def test_sources_are_copied(tmp_path):
    source = tmp_path / "uart.v"
    source.write_text("module uart; endmodule\n", encoding="utf-8")
    out = tmp_path / "out"

    code, _, err = _run(
        str(SVA / "external" / "root.yaml"),
        "-t",
        "sva",
        "--sva-steps",
        "1",
        "--sva-source",
        str(source),
        "-o",
        str(out),
    )

    assert code == 0, err
    assert (out / "sva_sources" / "uart.v").is_file()


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["-t", "verilog", "--sva-steps", "3"], "--sva-steps: only with -t sva"),
        (["-t", "mc2", "--delimiter", ";"], "--delimiter: only with -t sva"),
        (
            ["-t", "sva", "--sva-mode", "formal", "--sva-style", "concurrent"],
            "concurrent style is available for simulation only",
        ),
        (["-t", "sva", "--sva-depth", "5"], "depth applies to formal checks only"),
        (
            ["-t", "sva", "--sva-max-bound", "0"],
            "maximum bound must be a positive integer",
        ),
        (["-t", "sva", "--sva-steps", "-1"], "must be a non-negative integer"),
        (
            ["-t", "sva", "--sva-steps", "1", "--sva-inputs", "x.csv"],
            "give only one of --sva-inputs, --sva-steps",
        ),
        (
            ["-t", "sva", "--sva-replay", "t.yw", "--sva-steps", "1"],
            "give only one of --sva-steps, --sva-replay",
        ),
        (
            ["-t", "sva", "--sva-steps", "1", "--skip-lines", "1"],
            "--delimiter and --skip-lines apply to --sva-inputs",
        ),
        (
            ["-t", "sva", "--sva-steps", "1", "--output-suffix", "_x"],
            "--output-suffix is not supported",
        ),
    ],
)
def test_option_misuse_is_a_usage_error(args, message):
    code, _, err = _run(str(MONITORS), *args)

    assert code == 2
    assert message in err


@pytest.mark.parametrize(
    ("model", "args", "message"),
    [
        (MONITORS, [], "a model with inputs needs --sva-inputs FILE (inputs: u)"),
        (AUTONOMOUS, [], "a model without inputs needs --sva-steps N"),
        (MONITORS, ["--sva-steps", "2"], "--sva-steps is for models without inputs"),
        (
            AUTONOMOUS,
            ["--sva-inputs", str(INPUTS)],
            "--sva-inputs is for models with inputs",
        ),
    ],
)
def test_stimulus_that_does_not_fit_the_model_is_an_error(
    tmp_path, model, args, message
):
    code, _, err = _run(str(model), "-t", "sva", *args, "-o", str(tmp_path))

    assert code == 1
    assert message in err
    assert list(tmp_path.iterdir()) == []


def test_regenerating_removes_stimulus_files_the_new_run_does_not_produce(tmp_path):
    empty = tmp_path / "empty.csv"
    empty.write_text("u\n", encoding="utf-8")
    out = tmp_path / "out"
    _run(str(MONITORS), "-t", "sva", "--sva-inputs", str(INPUTS), "-o", str(out))
    assert (out / "monitors_inputs.hex").is_file()

    code, _, err = _run(
        str(MONITORS), "-t", "sva", "--sva-inputs", str(empty), "-o", str(out)
    )

    assert code == 0, err
    # Zero records: no hex file, so the one of the earlier run is removed.
    assert not (out / "monitors_inputs.hex").exists()
    assert (out / "monitors_inputs_decoded.csv").read_text(encoding="utf-8") == "u\n"
