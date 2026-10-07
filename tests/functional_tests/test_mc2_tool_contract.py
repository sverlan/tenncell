"""Opt-in end-to-end contract: generated MC2 files and nnc-sim traces run in MC2.

Set ``NNC_MC2_JAR`` to the path of ``MC2v2.0beta2.jar`` (and have ``java`` on
``PATH``) to run these tests; otherwise they are skipped.
"""

import os
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from nnc.cli import main as sim_main
from nnc.cli_transform import main as gen_main

FIXTURE_DIR = (
    Path(__file__).resolve().parents[1] / "fixtures" / "verification" / "mc2_tool"
)
MC2_JAR = os.environ.get("NNC_MC2_JAR")

pytestmark = pytest.mark.skipif(
    not MC2_JAR or shutil.which("java") is None,
    reason="set NNC_MC2_JAR and put java on PATH to run MC2 end-to-end tests",
)


def _generate_and_trace(out_dir: Path, delimiter: str) -> tuple[Path, Path]:
    model = FIXTURE_DIR / "fsm_counter.yaml"
    with patch("sys.argv", ["nnc-gen", str(model), "-t", "mc2", "-o", str(out_dir)]):
        assert gen_main() == 0

    stimulus = out_dir / "start.csv"
    stimulus.write_text(
        (FIXTURE_DIR / "start.csv").read_text(encoding="utf-8"), encoding="utf-8"
    )
    trace = out_dir / "trace.txt"
    with patch(
        "sys.argv",
        [
            "nnc-sim",
            str(model),
            str(stimulus),
            str(trace),
            "--csv-include-step",
            "--csv-include-initial",
            "--csv-delimiter",
            delimiter,
        ],
    ):
        assert sim_main() == 0
    return out_dir / "fsm_counter.mc2.pltl", trace


@pytest.mark.parametrize(("delimiter", "options"), [(";", ["-snoopy"]), (" ", [])])
def test_mc2_checks_generated_queries_on_simulated_trace(tmp_path, delimiter, options):
    queries, trace = _generate_and_trace(tmp_path, delimiter)

    result = subprocess.run(
        ["java", "-jar", str(MC2_JAR), "stoch", str(trace), str(queries), *options, "-quiet"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    # Query order matches fsm_counter.mc2.ids.
    assert result.stdout.strip() == "1.0,true,true,1.0,0.0", result.stdout + result.stderr
