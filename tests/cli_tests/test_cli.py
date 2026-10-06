"""CLI contract tests for `nnc-sim` simulation."""

import csv
import json
import subprocess
import sys
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from nnc.cli import main
from nnc._version import __version__


def test_sim_cli_version():
    with patch("sys.argv", ["nnc-sim", "--version"]):
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            try:
                main()
            except SystemExit as exit_error:
                assert exit_error.code == 0

    assert mock_stdout.getvalue() == f"nnc-sim {__version__}\n"


def test_compute_mode_runs_without_csv_input():
    input_file = (
        Path(__file__).resolve().parents[1] / "fixtures" / "cli" / "compute_mode.yaml"
    )

    with patch("sys.argv", ["nnc-sim", str(input_file), "-c", "-s", "1"]):
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            exit_code = main()

    assert exit_code == 0
    assert json.loads(mock_stdout.getvalue()) == [
        {"Message": "Running in continuous compute mode for 1 steps"},
        {"Step": 0},
        {"Step": 1},
    ]


def test_compute_mode_writes_csv_output_without_double_cr():
    input_file = (
        Path(__file__).resolve().parents[1] / "fixtures" / "cli" / "compute_mode.yaml"
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "nnc",
            str(input_file),
            "-c",
            "-s",
            "1",
            "--csv",
        ],
        check=True,
        capture_output=True,
    )

    stdout = result.stdout
    assert b"\r\r\n" not in stdout
    assert stdout.splitlines() == [b"step", b"0", b"1"]


def test_compute_mode_csv_can_suppress_initial_row():
    input_file = (
        Path(__file__).resolve().parents[1] / "fixtures" / "cli" / "compute_mode.yaml"
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "nnc",
            str(input_file),
            "-c",
            "-s",
            "1",
            "--csv",
            "--csv-no-initial",
        ],
        check=True,
        capture_output=True,
    )

    assert result.stdout.splitlines() == [b"step", b"1"]


def test_io_mode_writes_csv_output():
    input_file = (
        Path(__file__).resolve().parents[1] / "fixtures" / "cli" / "io_mode.yaml"
    )

    with TemporaryDirectory() as tmp_dir:
        tmp_dir = Path(tmp_dir)
        csv_input = tmp_dir / "input.csv"
        csv_output = tmp_dir / "output.csv"
        csv_input.write_text("u\n1\n0\n", encoding="utf-8")

        with patch(
            "sys.argv",
            ["nnc-sim", str(input_file), str(csv_input), str(csv_output)],
        ):
            exit_code = main()

        with csv_output.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

    assert exit_code == 0
    assert list(rows[0].keys()) == ["x", "y", "z"]
    assert len(rows) == 2


def test_io_mode_csv_options_apply_to_input_and_output():
    input_file = (
        Path(__file__).resolve().parents[1] / "fixtures" / "cli" / "io_mode.yaml"
    )

    with TemporaryDirectory() as tmp_dir:
        tmp_dir = Path(tmp_dir)
        csv_input = tmp_dir / "input.csv"
        csv_output = tmp_dir / "output.csv"
        csv_input.write_text("u\n1.25\n", encoding="utf-8")

        with patch(
            "sys.argv",
            [
                "nnc-sim",
                str(input_file),
                str(csv_input),
                str(csv_output),
                "--csv-include-initial",
                "--csv-delimiter",
                ";",
                "--csv-precision",
                "2",
            ],
        ):
            exit_code = main()

        output = csv_output.read_text(encoding="utf-8")

    assert exit_code == 0
    assert output.splitlines()[0] == "x;y;z"
    assert output.splitlines()[1] == "0.00;0.00;0.00"
    assert len(output.splitlines()) == 3


def test_cli_returns_one_on_runtime_error():
    """Runtime errors should produce stderr output and exit code 1."""
    input_file = (
        Path(__file__).resolve().parents[1] / "fixtures" / "cli" / "io_mode.yaml"
    )

    with patch("sys.argv", ["nnc-sim", str(input_file), "-c"]):
        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            exit_code = main()

    assert exit_code == 1
    assert "Cannot run in continuous compute mode with input variables" in (
        mock_stderr.getvalue()
    )
