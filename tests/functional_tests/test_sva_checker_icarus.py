"""Opt-in Icarus compilation contracts for the SVA checker shell."""

import os
import subprocess
from pathlib import Path

import pytest
from sva_helpers import SVA_MODELS, SVA_ROOT, write_sva_output

ROOT = Path(__file__).resolve().parents[1]
VERILOG_GOLDENS = ROOT / "fixtures" / "transformers" / "verilog" / "expected"
IVERILOG = os.environ.get("NNC_IVERILOG")

pytestmark = pytest.mark.skipif(
    not IVERILOG or not Path(IVERILOG).is_file(),
    reason="set NNC_IVERILOG to the iverilog executable to compile SVA checkers",
)


def _run(args: list[str]) -> subprocess.CompletedProcess:
    """Run Icarus with its DLL directories on PATH."""
    tool_dir = Path(IVERILOG).parent
    env = {
        **os.environ,
        "PATH": os.pathsep.join(
            [str(tool_dir), str(tool_dir.parent / "lib"), os.environ["PATH"]]
        ),
    }
    return subprocess.run(
        args, capture_output=True, text=True, env=env, timeout=120, check=False
    )


def _version() -> str:
    """Return the first Icarus version line for failure diagnostics."""
    return _run([IVERILOG, "-V"]).stdout.splitlines()[0]


def test_all_verilog_goldens_compile(tmp_path):
    sources = sorted(VERILOG_GOLDENS.rglob("*.sv"))
    for index, source in enumerate(sources):
        result = _run(
            [
                IVERILOG,
                "-g2012",
                "-i",
                "-tnull",
                "-o",
                str(tmp_path / f"golden_{index}.vvp"),
                str(source),
            ]
        )
        assert result.returncode == 0, (
            f"{source}\n{_version()}\n{result.stdout}{result.stderr}"
        )


@pytest.mark.parametrize("model", SVA_MODELS)
def test_generated_checker_and_rtl_closure_compile(tmp_path, model):
    _, sources = write_sva_output(SVA_ROOT / model, tmp_path / "out")

    for define in ([], ["-DFORMAL"]):
        label = "formal" if define else "simulation"
        result = _run(
            [
                IVERILOG,
                "-g2012",
                *define,
                "-tnull",
                "-o",
                str(tmp_path / f"checker_{label}.vvp"),
                *map(str, sources),
            ]
        )
        assert result.returncode == 0, (
            f"{model} {label}: {_version()}\n{result.stdout}{result.stderr}"
        )
