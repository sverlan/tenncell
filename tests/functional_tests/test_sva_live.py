"""Opt-in contract: liveness of unbounded ``eventually`` (SymbiYosys ``live`` task).

The ``live`` task needs the ``suprove`` engine, which only the Linux
oss-cad-suite ships. Set ``NNC_SBY_LIVE`` to a command running that ``sby``,
split on whitespace; it is run in the output directory, for example
``wsl -e /mnt/c/tools/oss-cad-suite-linux/bin/sby`` on Windows.
Each test keeps the listed properties of the liveness fixture.
"""

import dataclasses
import os
import subprocess
from pathlib import Path

import pytest

from nnc.cli_transform import (
    _collect_import_closure,
    _parse_verification_configs,
    _parse_verilog_configs,
)
from nnc.model.system import NncSystem
from nnc.transformers import SvaTransformer
from nnc.verification.sva import SvaOptions

MODEL = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "verification"
    / "sva"
    / "formal"
    / "liveness.yaml"
)
SBY_LIVE = os.environ.get("NNC_SBY_LIVE")

pytestmark = pytest.mark.skipif(
    not SBY_LIVE,
    reason="set NNC_SBY_LIVE to a command running sby with suprove to run liveness checks",
)


def _live(out: Path, *keep: str) -> str:
    """Generate the formal files keeping ``keep``, run the live task and
    return its status word (``PASS`` or ``FAIL``)."""
    assert SBY_LIVE is not None
    cache: dict = {}
    import_paths = [str(MODEL.parent)]
    system = NncSystem.from_yaml(
        str(MODEL), import_paths=import_paths, _raw_data_cache=cache
    )
    bound = _parse_verification_configs([system], cache)[system.source_path]
    assert bound is not None
    bound = dataclasses.replace(
        bound, properties=tuple(p for p in bound.properties if p.property.id in keep)
    )
    transformer = SvaTransformer(
        SvaOptions(mode="formal"),
        _parse_verilog_configs(_collect_import_closure(system), cache, import_paths),
        {system.source_path: bound},
    )
    transformer.write(transformer.generate(system), out)
    run = subprocess.run(
        [*SBY_LIVE.split(), "-f", f"{MODEL.stem}.sby", "live"],
        capture_output=True,
        text=True,
        cwd=out,
        timeout=300,
        check=False,
    )
    status = out / f"{MODEL.stem}_live" / "status"
    assert status.is_file(), run.stdout + run.stderr
    return status.read_text(encoding="utf-8").split()[0]


@pytest.mark.parametrize("prop", ["reaches_one", "late_zero"])
def test_a_property_reached_on_every_run_passes(tmp_path, prop):
    assert _live(tmp_path, prop) == "PASS"


@pytest.mark.parametrize("prop", ["reaches_two", "input_reaches_max"])
def test_a_property_some_run_never_reaches_fails(tmp_path, prop):
    # input_reaches_max: the free input may avoid 5 forever.
    assert _live(tmp_path, prop) == "FAIL"


def test_a_failing_safety_property_does_not_hide_a_liveness_failure(tmp_path):
    # SymbiYosys would assume never_one in live mode, leaving no run and a
    # vacuous PASS; the live task removes the other assertions instead.
    assert _live(tmp_path, "reaches_two", "never_one") == "FAIL"


def test_one_failing_liveness_property_fails_the_task(tmp_path):
    # The task reports one status for all liveness properties: all must hold.
    assert _live(tmp_path, "reaches_one", "reaches_two") == "FAIL"
