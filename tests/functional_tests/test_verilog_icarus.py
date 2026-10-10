"""Opt-in contract: generated RTL compiles and behaves correctly in Icarus Verilog.

Set ``NNC_IVERILOG`` to the ``iverilog`` executable (``vvp`` must be in the same
directory, e.g. ``C:/tools/oss-cad-suite/bin/iverilog.exe``) to run these
tests; otherwise they are skipped.
"""

import os
import subprocess
from pathlib import Path

import pytest

from nnc.cli_transform import _collect_import_closure, _parse_verilog_configs
from nnc.model.system import NncSystem
from nnc.transformers import VerilogTransformer

FIXTURE_ROOT = (
    Path(__file__).resolve().parents[1] / "fixtures" / "transformers" / "verilog"
)
IVERILOG = os.environ.get("NNC_IVERILOG")

pytestmark = pytest.mark.skipif(
    not IVERILOG or not Path(IVERILOG).is_file(),
    reason="set NNC_IVERILOG to the iverilog executable to run Icarus RTL tests",
)


def _tool_env() -> dict[str, str]:
    """PATH with the tool directory and its sibling lib/ (Windows DLLs)."""
    tool_dir = Path(IVERILOG).parent
    extra = [str(tool_dir), str(tool_dir.parent / "lib")]
    return {**os.environ, "PATH": os.pathsep.join([*extra, os.environ["PATH"]])}


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        args, capture_output=True, text=True, env=_tool_env(), timeout=120, check=False
    )


def _generate(model: Path, out_dir: Path) -> list[Path]:
    """Write the RTL closure of a model, as nnc-gen -t verilog does."""
    raw_data_cache: dict = {}
    import_paths = [str(model.parent)]
    system = NncSystem.from_yaml(
        str(model), import_paths=import_paths, _raw_data_cache=raw_data_cache
    )
    closure = _collect_import_closure(system)
    transformer = VerilogTransformer(
        _parse_verilog_configs(closure, raw_data_cache, import_paths)
    )
    files = []
    for item in closure:
        path = out_dir / f"{Path(item.source_path).stem}.sv"
        path.write_text(transformer.transform(item), encoding="utf-8")
        files.append(path)
    return files


def _version() -> str:
    return _run([IVERILOG, "-V"]).stdout.splitlines()[0]


@pytest.mark.parametrize(
    ("model", "testbench"),
    [
        ("negative_literals.yaml", "negative_literals_tb.sv"),
        ("logic_outputs.yaml", "logic_outputs_tb.sv"),
        ("logic_output_import/parent.yaml", "logic_output_import_tb.sv"),
        ("signed_logic_storage.yaml", "signed_logic_tb.sv"),
        ("fixed_point_arithmetic.yaml", "fixed_point_arithmetic_tb.sv"),
    ],
)
def test_generated_rtl_simulates_correctly(tmp_path, model, testbench):
    sources = _generate(FIXTURE_ROOT / "input" / model, tmp_path)
    binary = tmp_path / "sim.vvp"

    compiled = _run(
        [
            IVERILOG,
            "-g2012",
            "-o",
            str(binary),
            *map(str, sources),
            str(FIXTURE_ROOT / "sim" / testbench),
        ]
    )
    assert compiled.returncode == 0, f"{_version()}\n{compiled.stderr}"

    vvp = str(Path(IVERILOG).with_name("vvp" + Path(IVERILOG).suffix))
    run = _run([vvp, "-n", str(binary)])

    assert "RESULT PASS" in run.stdout, f"{_version()}\n{run.stdout}{run.stderr}"
