"""Opt-in contract: SymbiYosys witnesses replayed in RTL simulation.

Needs ``NNC_SBY`` (the ``sby`` executable) and ``NNC_IVERILOG``. Each case
finds a witness with SymbiYosys (one property kept), replays it with
``--sva-replay`` in Icarus, and compares with ``native`` on the decoded inputs
(or the same number of steps). The replay must reproduce the witness on its
last row; ``native`` may agree or diverge (fixed-point RTL), which is reported,
not a replay failure.
"""

import dataclasses
import os
from pathlib import Path

import pytest
from sva_helpers import run_tool

from nnc.cli_transform import (
    _collect_import_closure,
    _parse_verification_configs,
    _parse_verilog_configs,
)
from nnc.cli_verify import simulate_inputs, simulate_steps
from nnc.model.system import NncSystem
from nnc.transformers import SvaTransformer
from nnc.verification.generic_properties.native import check_properties
from nnc.verification.sva import SvaOptions
from nnc.verification.sva_stimulus import SvaStimulusSource

SVA = Path(__file__).resolve().parents[1] / "fixtures" / "verification" / "sva"
SBY = os.environ.get("NNC_SBY")
IVERILOG = os.environ.get("NNC_IVERILOG")

pytestmark = pytest.mark.skipif(
    not (SBY and Path(SBY).is_file() and IVERILOG and Path(IVERILOG).is_file()),
    reason="set NNC_SBY and NNC_IVERILOG to replay SymbiYosys witnesses",
)


def _load(model: Path, prop: str):
    cache: dict = {}
    import_paths = [str(model.parent)]
    system = NncSystem.from_yaml(
        str(model), import_paths=import_paths, _raw_data_cache=cache
    )
    bound = _parse_verification_configs([system], cache)[system.source_path]
    assert bound is not None
    bound = dataclasses.replace(
        bound, properties=tuple(p for p in bound.properties if p.property.id == prop)
    )
    configs = _parse_verilog_configs(
        _collect_import_closure(system), cache, import_paths
    )
    return system, configs, bound


def _witness(model: Path, prop: str, task: str, depth: int, out: Path) -> Path:
    system, configs, bound = _load(model, prop)
    transformer = SvaTransformer(
        SvaOptions(mode="formal", depth=depth), configs, {system.source_path: bound}
    )
    transformer.write(transformer.generate(system), out)
    run_tool(SBY, ["-f", f"{model.stem}.sby", task], cwd=out)
    witnesses = sorted((out / f"{model.stem}_{task}" / "engine_0").glob("trace*.yw"))
    assert witnesses, f"no witness for {prop} ({task})"
    return witnesses[0]


def _rows(output, model: Path) -> int:
    testbench = output.files[f"{model.stem}_tb.sv"]
    return int(testbench.split("RECORDS = ")[1].split(";")[0])


def _replay(model: Path, prop: str, witness: Path, out: Path):
    """Replay a witness in Icarus; return the RTL lines and native's lines."""
    system, configs, bound = _load(model, prop)
    transformer = SvaTransformer(
        SvaOptions(),
        configs,
        {system.source_path: bound},
        SvaStimulusSource(witness=witness),
    )
    output = transformer.generate(system)
    transformer.write(output, out)
    sources = sorted(path.name for path in out.glob("*.sv"))
    compiled = run_tool(IVERILOG, ["-g2012", "-o", "sim.vvp", *sources], cwd=out)
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    vvp = str(Path(IVERILOG).with_name("vvp" + Path(IVERILOG).suffix))
    run = run_tool(vvp, ["-n", "sim.vvp"], cwd=out)
    rtl = [line for line in run.stdout.splitlines() if line.startswith("SVA_RESULT")]
    reproduced = f"SVA_REPLAY reproduced on row {_rows(output, model)}"
    assert (reproduced in run.stdout) == (run.returncode == 0), run.stdout + run.stderr

    native_system, _, _ = _load(model, prop)
    decoded = out / f"{model.stem}_inputs_decoded.csv"
    if decoded.is_file():
        trace = simulate_inputs(native_system, decoded, ",")
    else:
        rows = int(
            output.files[f"{model.stem}_tb.sv"].split("RECORDS = ")[1].split(";")[0]
        )
        trace = simulate_steps(native_system, rows)
    native = [
        f"SVA_RESULT {r.id} {r.status} {'-' if r.trigger_row is None else r.trigger_row} "
        f"{'-' if r.reported_row is None else r.reported_row}"
        for r in check_properties(bound, native_system, trace, "strict")
    ]
    return rtl, native, run


@pytest.mark.parametrize(
    ("model", "prop", "depth", "expected"),
    [
        # A free input reaches its forbidden value on row 1.
        ("formal/follow.yaml", "input_never_max", 6, "input_never_max fail - 1"),
        # No input: the witness length gives the rows.
        ("formal/counter.yaml", "never_five", 8, "never_five fail - 5"),
        ("formal/counter.yaml", "response_late", 8, "response_late fail 1 3"),
    ],
)
def test_bmc_counterexample_is_reproduced_and_native_agrees(
    tmp_path, model, prop, depth, expected
):
    witness = _witness(SVA / model, prop, "bmc", depth, tmp_path / "formal")

    rtl, native, run = _replay(SVA / model, prop, witness, tmp_path / "replay")

    assert rtl == [f"SVA_RESULT {expected}"]
    assert "SVA_REPLAY reproduced on row" in run.stdout and run.returncode == 0
    assert native == rtl


def test_cover_witness_is_reproduced(tmp_path):
    model = SVA / "formal" / "counter.yaml"
    witness = _witness(model, "cover_late_three", "cover", 8, tmp_path / "formal")

    rtl, native, run = _replay(model, "cover_late_three", witness, tmp_path / "replay")

    assert rtl == ["SVA_RESULT cover_late_three covered - -"]
    assert "SVA_REPLAY reproduced on row 3" in run.stdout and run.returncode == 0
    assert native == rtl


def test_fixed_point_divergence_is_reported_not_a_replay_failure(tmp_path):
    # The RTL overflows Q8.8 at row 7 (x = 128); native, in floating point,
    # does not. The replay reproduces the RTL failure; native diverges.
    model = SVA / "monitors" / "divergence.yaml"
    witness = _witness(model, "x_positive", "bmc", 10, tmp_path / "formal")

    rtl, native, run = _replay(model, "x_positive", witness, tmp_path / "replay")

    assert rtl == ["SVA_RESULT x_positive fail - 7"]
    assert "SVA_REPLAY reproduced on row 7" in run.stdout and run.returncode == 0
    assert native == ["SVA_RESULT x_positive pass - -"]


def test_a_witness_that_does_not_belong_to_the_checks_is_not_reproduced(tmp_path):
    # The witness of input_never_max matches follow.yaml's ports, but replayed
    # against a checker keeping only a true property nothing fails on its row:
    # compatibility is structural, the testbench reports it.
    model = SVA / "formal" / "follow.yaml"
    witness = _witness(model, "input_never_max", "bmc", 6, tmp_path / "formal")

    rtl, _, run = _replay(model, "x_follows_input", witness, tmp_path / "replay")

    assert rtl == ["SVA_RESULT x_follows_input pass - -"]
    assert "SVA_REPLAY NOT reproduced" in run.stdout + run.stderr
    assert run.returncode != 0
