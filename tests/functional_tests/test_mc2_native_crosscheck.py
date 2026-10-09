"""Opt-in contract: MC2 agrees with the native checker on generic properties.

Set ``NNC_MC2_JAR`` to the path of ``MC2v2.0beta2.jar`` (and have ``java`` on
``PATH``) to run these tests; otherwise they are skipped.
"""

import dataclasses
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from nnc import NncSystem
from nnc.cli_transform import _parse_verification_configs
from nnc.cli_verify import read_trace
from nnc.verification.config import EVENTUALLY
from nnc.verification.generic_properties.native import (
    COVERED,
    FAIL,
    NOT_COVERED,
    PASS,
    PENDING,
    check_properties,
)
from nnc.verification.mc2 import render_mc2

FIXTURE_DIR = (
    Path(__file__).resolve().parents[1] / "fixtures" / "verification" / "mc2_crosscheck"
)
TRACES = sorted((FIXTURE_DIR / "traces").glob("*.txt"))
MC2_JAR = os.environ.get("NNC_MC2_JAR")

pytestmark = pytest.mark.skipif(
    not MC2_JAR or shutil.which("java") is None,
    reason="set NNC_MC2_JAR and put java on PATH to run MC2 end-to-end tests",
)


def _expected_mc2(status: str, kind: str) -> float:
    if status == PENDING:
        # Weak MC2 counts open obligations as satisfied, except unbounded
        # `eventually`, which MC2 checks strictly.
        return 0.0 if kind == EVENTUALLY else 1.0
    return {PASS: 1.0, FAIL: 0.0, COVERED: 1.0, NOT_COVERED: 0.0}[status]


@pytest.mark.parametrize("semantics", ["strict", "weak"])
@pytest.mark.parametrize("trace_path", TRACES, ids=[path.stem for path in TRACES])
def test_mc2_matches_native(tmp_path, semantics, trace_path):
    model = FIXTURE_DIR / "model.yaml"
    raw_cache: dict = {}
    system = NncSystem.from_yaml(str(model), _raw_data_cache=raw_cache)
    bound = _parse_verification_configs([system], raw_cache)[system.source_path]
    bound = dataclasses.replace(
        bound, config=dataclasses.replace(bound.config, trace_semantics=semantics)
    )
    artifacts = render_mc2(bound, system.source_locations)
    queries = tmp_path / "queries.pltl"
    queries.write_text(artifacts.files()[".mc2.pltl"], encoding="utf-8")

    result = subprocess.run(
        [
            "java",
            "-jar",
            str(MC2_JAR),
            "stoch",
            str(trace_path),
            str(queries),
            "-quiet",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    mc2_values = [float(value) for value in result.stdout.strip().split(",")]

    trace = read_trace(trace_path, {"p", "t"}, " ")
    native = check_properties(bound, system, trace)
    assert [r.id for r in native] == list(artifacts.ids)
    mismatches = [
        (r.id, r.status, value)
        for r, value in zip(native, mc2_values, strict=True)
        if abs(value - _expected_mc2(r.status, r.kind)) > 1e-9
    ]
    assert mismatches == [], result.stdout + result.stderr
