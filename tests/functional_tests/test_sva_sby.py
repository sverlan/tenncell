"""Opt-in contract: formal checks with SymbiYosys (bmc and cover tasks).

Set ``NNC_SBY`` to the ``sby`` executable of an oss-cad-suite (with yosys, the
yosys-slang plugin and the yices solver next to it) to run these tests.
Each test keeps one property of a fixture (BMC stops at the first failing
assertion) and checks the row where SymbiYosys finds the violation through the
depth contract: ``--sva-depth D`` explores rows ``0..D-1``.
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
from nnc.model.system import NncSystem
from nnc.transformers import SvaTransformer
from nnc.verification.sva import SvaOptions

FORMAL = (
    Path(__file__).resolve().parents[1] / "fixtures" / "verification" / "sva" / "formal"
)
SBY = os.environ.get("NNC_SBY")

pytestmark = pytest.mark.skipif(
    not SBY or not Path(SBY).is_file(),
    reason="set NNC_SBY to the sby executable to run formal checks",
)


def _sby(
    model: Path,
    depth: int,
    task: str,
    out: Path,
    only: str | tuple[str, ...] | None = None,
) -> str:
    """Generate the formal files (keeping one property), run one task and
    return its status word (``PASS`` or ``FAIL``)."""
    cache: dict = {}
    import_paths = [str(model.parent)]
    system = NncSystem.from_yaml(
        str(model), import_paths=import_paths, _raw_data_cache=cache
    )
    bound = _parse_verification_configs([system], cache)[system.source_path]
    assert bound is not None
    if only is not None:
        bound = dataclasses.replace(
            bound,
            properties=tuple(
                p
                for p in bound.properties
                if p.property.id in ((only,) if isinstance(only, str) else only)
            ),
        )
    transformer = SvaTransformer(
        SvaOptions(mode="formal", depth=depth),
        _parse_verilog_configs(_collect_import_closure(system), cache, import_paths),
        {system.source_path: bound},
    )
    transformer.write(transformer.generate(system), out)
    run = run_tool(SBY, ["-f", f"{model.stem}.sby", task], cwd=out)
    status = out / f"{model.stem}_{task}" / "status"
    assert status.is_file(), run.stdout + run.stderr
    return status.read_text(encoding="utf-8").split()[0]


def test_a_true_property_passes(tmp_path):
    assert _sby(FORMAL / "counter.yaml", 20, "bmc", tmp_path, "below_hundred") == "PASS"


@pytest.mark.parametrize(
    ("prop", "row"),
    [
        ("never_zero", 0),  # depth 1 explores row 0 only
        ("never_one", 1),  # depth 2 explores rows 0 and 1
        ("never_five", 5),
        ("late_window", 3),  # x == 1 at row 1 is before the window
        ("response_late", 3),  # satisfaction at age 0 is before the window
        ("response_after_three", 5),  # checked at the trigger's age 3
        ("stays_small", 6),
    ],
)
def test_a_violation_is_found_exactly_from_its_row(tmp_path, prop, row):
    # Depth row + 1 explores the failing row; depth row stops just before it
    # (an obligation completing after the horizon is not checked).
    model = FORMAL / "counter.yaml"

    assert _sby(model, row + 1, "bmc", tmp_path / "found", prop) == "FAIL"
    if row > 0:
        assert _sby(model, row, "bmc", tmp_path / "before", prop) == "PASS"


def test_cover_respects_from_step(tmp_path):
    model = FORMAL / "counter.yaml"

    # x == 3 at row 3: reached with 4 rows, not with 3.
    assert _sby(model, 4, "cover", tmp_path / "three", "cover_late_three") == "PASS"
    assert _sby(model, 3, "cover", tmp_path / "early", "cover_late_three") == "FAIL"
    # x == 1 only at row 1, before from_step 2: never reached.
    assert _sby(model, 10, "cover", tmp_path / "one", "cover_late_one") == "FAIL"


@pytest.mark.parametrize("prop", ["x_follows_input", "input_in_range", "x_in_range"])
def test_constrained_free_inputs_keep_properties_on_aligned_rows(tmp_path, prop):
    # Free inputs within the environment range, possibly different on every
    # row: the copies stay aligned with the rows and the assumption bounds
    # the live port.
    assert _sby(FORMAL / "follow.yaml", 12, "bmc", tmp_path, prop) == "PASS"


def test_free_inputs_reach_every_value_of_the_range(tmp_path):
    assert _sby(FORMAL / "follow.yaml", 3, "bmc", tmp_path, "input_never_max") == "FAIL"


@pytest.mark.parametrize("prop", ["bounded", "window", "flips", "comes_back", "stays"])
def test_true_properties_are_proved_by_both_engines(tmp_path, prop):
    # `window` and `stays` need the monitor invariants (step and age counters
    # at most their limits) for k-induction.
    model = FORMAL / "toggle.yaml"

    assert _sby(model, 4, "prove_kind", tmp_path / "kind", prop) == "PASS"
    assert _sby(model, 4, "prove_pdr", tmp_path / "pdr", prop) == "PASS"


def test_k_induction_needs_the_history_length_pdr_does_not(tmp_path):
    # 20 rows of pending bits: induction length 2 + 2 rows is too short, and
    # k-induction answers UNKNOWN, never PASS; 22 rows are enough.
    model = FORMAL / "toggle.yaml"

    assert _sby(model, 2, "prove_kind", tmp_path / "short", "long_window") == "UNKNOWN"
    assert _sby(model, 2, "prove_pdr", tmp_path / "pdr", "long_window") == "PASS"
    assert _sby(model, 22, "prove_kind", tmp_path / "long", "long_window") == "PASS"


@pytest.mark.parametrize("prop", ["never_five", "below_hundred"])
def test_false_properties_are_never_proved(tmp_path, prop):
    # never_five fails at row 5; below_hundred holds for the first 100 rows
    # only (x keeps counting): PDR finds the counterexample, k-induction with a
    # short induction length cannot decide.
    model = FORMAL / "counter.yaml"

    assert _sby(model, 3, "prove_pdr", tmp_path / "pdr", prop) == "FAIL"
    assert _sby(model, 3, "prove_kind", tmp_path / "kind", prop) != "PASS"


@pytest.mark.parametrize(
    ("keep", "status"),
    [
        (("bounded", "reaches_two"), "PASS"),  # the false liveness is not checked
        (("never_one", "reaches_one"), "FAIL"),  # the safety failure is still found
    ],
)
@pytest.mark.parametrize("task", ["bmc", "prove_kind", "prove_pdr"])
def test_safety_tasks_ignore_the_liveness_cell(tmp_path, keep, status, task):
    # The checker instantiates the $live helper; outside the live task
    # SymbiYosys drops it, and the safety assertions are checked as usual.
    assert _sby(FORMAL / "liveness.yaml", 4, task, tmp_path, keep) == status


def test_cover_runs_next_to_the_liveness_cell(tmp_path):
    keep = ("reaches_two", "covers_one")
    assert _sby(FORMAL / "liveness.yaml", 4, "cover", tmp_path, keep) == "PASS"
