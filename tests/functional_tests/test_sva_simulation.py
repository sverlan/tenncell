"""Opt-in contract: the generated SVA testbench gives native's results.

Set ``NNC_IVERILOG`` to the ``iverilog`` executable (``vvp`` in the same
directory) to run these tests in Icarus. Set ``NNC_VERILATOR`` to
``verilator_bin`` to also run a few of them as Verilator binaries; that needs
``make`` and ``g++`` on ``PATH`` (``NNC_CXX_PATH`` may list directories to put
in front, for example the msys64 ``mingw64/bin`` and ``usr/bin``).
"""

import dataclasses
import os
import shutil
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

ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "verification"
FIXTURE = ROOT / "sva" / "monitors"
MC2_TRACES = ROOT / "mc2_crosscheck" / "traces"
IVERILOG = os.environ.get("NNC_IVERILOG")
VERILATOR = os.environ.get("NNC_VERILATOR")
CXX_PATH = os.environ.get("NNC_CXX_PATH", "")
ICARUS, VERILATOR_SIM = "icarus", "verilator"

needs_icarus = pytest.mark.skipif(
    not IVERILOG or not Path(IVERILOG).is_file(),
    reason="set NNC_IVERILOG to the iverilog executable to run SVA monitors",
)


def _cxx_env() -> dict[str, str]:
    return {"PATH": os.pathsep.join([CXX_PATH, os.environ["PATH"]])} if CXX_PATH else {}


def _has_cxx_tools() -> bool:
    path = os.pathsep.join([CXX_PATH, os.environ["PATH"]])
    return all(shutil.which(tool, path=path) for tool in ("make", "g++"))


needs_verilator = pytest.mark.skipif(
    not VERILATOR or not Path(VERILATOR).is_file() or not _has_cxx_tools(),
    reason="set NNC_VERILATOR (and make/g++ on PATH or NNC_CXX_PATH) to run "
    "SVA monitors as Verilator binaries",
)


def _load(model: Path, semantics: str):
    """Load a model with the given global trace semantics."""
    cache: dict = {}
    import_paths = [str(model.parent)]
    system = NncSystem.from_yaml(
        str(model), import_paths=import_paths, _raw_data_cache=cache
    )
    bound = _parse_verification_configs([system], cache)[system.source_path]
    assert bound is not None
    bound = dataclasses.replace(
        bound, config=dataclasses.replace(bound.config, trace_semantics=semantics)
    )
    return system, cache, import_paths, bound


def _lines(results) -> list[str]:
    """Native results in the checker's line format."""
    lines = []
    for result in results:
        trigger = "-" if result.trigger_row is None else result.trigger_row
        reported = "-" if result.reported_row is None else result.reported_row
        lines.append(f"SVA_RESULT {result.id} {result.status} {trigger} {reported}")
        for obligation in result.open_obligations:
            row = "end" if obligation.trigger_row is None else obligation.trigger_row
            lines.append(f"SVA_OPEN {result.id} {row}")
    return lines


def _simulate(
    model: Path,
    semantics: str,
    source: SvaStimulusSource,
    out: Path,
    simulator: str = ICARUS,
):
    """Generate the SVA files with the testbench, run them, and return the
    result lines, the run and the native lines."""
    system, cache, import_paths, bound = _load(model, semantics)
    transformer = SvaTransformer(
        SvaOptions(),
        _parse_verilog_configs(_collect_import_closure(system), cache, import_paths),
        {system.source_path: bound},
        source,
    )
    output = transformer.generate(system)
    transformer.write(output, out)
    sources = sorted(path.name for path in out.glob("*.sv"))
    if simulator == ICARUS:
        compiled = run_tool(IVERILOG, ["-g2012", "-o", "sim.vvp", *sources], cwd=out)
        assert compiled.returncode == 0, compiled.stdout + compiled.stderr
        vvp = str(Path(IVERILOG).with_name("vvp" + Path(IVERILOG).suffix))
        run = run_tool(vvp, ["-n", "sim.vvp"], cwd=out)  # finds <stem>_inputs.hex
    else:
        top = f"{system.module_config.name}_tb"
        root = os.environ.get(
            "VERILATOR_ROOT", str(Path(VERILATOR).parent.parent / "share" / "verilator")
        )
        compiled = run_tool(
            VERILATOR,
            ["--binary", "--timing", "-Wno-fatal", "--top-module", top, *sources],
            env={**_cxx_env(), "VERILATOR_ROOT": root},
            cwd=out,
        )
        assert compiled.returncode == 0, compiled.stdout + compiled.stderr
        binary = out / "obj_dir" / f"V{top}"
        if not binary.is_file():
            binary = binary.with_suffix(".exe")  # Windows
        run = run_tool(str(binary), [], env=_cxx_env(), cwd=out)
    lines = [
        line
        for line in run.stdout.splitlines()
        if line.startswith(("SVA_RESULT", "SVA_OPEN"))
    ]

    # Native on the same (decoded) inputs, or the same number of steps.
    native_system, _, _, _ = _load(model, semantics)
    if source.inputs is not None:
        decoded = out / f"{model.stem}_inputs_decoded.csv"
        trace = simulate_inputs(native_system, decoded, ",")
    else:
        assert source.steps is not None
        trace = simulate_steps(native_system, source.steps)
    expected = _lines(check_properties(bound, native_system, trace, semantics))
    return lines, run, expected


def _assert_agrees(lines, run, expected, label):
    assert lines == expected, f"{label}\n{run.stdout}{run.stderr}"
    failed = any(line.split()[2] == "fail" for line in expected)
    assert (run.returncode != 0) == failed, f"{label}\n{run.stdout}{run.stderr}"


@needs_icarus
@pytest.mark.parametrize("semantics", ["strict", "weak"])
def test_monitors_match_native(tmp_path, semantics):
    records = (FIXTURE / "inputs.csv").read_text(encoding="utf-8").splitlines()

    # 0 records: row 0 only; 6: every record of inputs.csv. Each count ends the
    # run at a different point of the windows and pending obligations.
    for count in range(7):
        inputs = tmp_path / f"inputs_{count}.csv"
        inputs.write_text("\n".join(records[: count + 1]) + "\n", encoding="utf-8")
        lines, run, expected = _simulate(
            FIXTURE / "monitors.yaml",
            semantics,
            SvaStimulusSource(inputs=inputs),
            tmp_path / f"out_{count}",
        )
        _assert_agrees(lines, run, expected, f"{count} records")


@needs_icarus
@pytest.mark.parametrize("semantics", ["strict", "weak"])
@pytest.mark.parametrize("steps", [0, 1, 20])
def test_autonomous_model_matches_native(tmp_path, semantics, steps):
    # 20 steps run past the saturating step counter (it stops at row 11).
    lines, run, expected = _simulate(
        FIXTURE / "autonomous.yaml",
        semantics,
        SvaStimulusSource(steps=steps),
        tmp_path / "out",
    )
    _assert_agrees(lines, run, expected, f"{steps} steps")


@needs_icarus
def test_imported_input_uses_the_value_given_to_the_child(tmp_path):
    model = ROOT / "sva" / "imported_input" / "parent.yaml"

    lines, run, expected = _simulate(
        model,
        "strict",
        SvaStimulusSource(steps=3),
        tmp_path / "out",
    )

    assert expected == [
        "SVA_RESULT child_saw_its_input pass - -",
        "SVA_RESULT input_lags_parent_state pass - -",
    ]
    _assert_agrees(lines, run, expected, "imported input connected to parent state")


@needs_icarus
def test_root_input_reaches_child_and_parent_in_the_same_step(tmp_path):
    # The input record of a step is given to the child in that step, like
    # the parent's rules read it: on row k both hold record k.
    inputs = tmp_path / "inputs.csv"
    inputs.write_text("u\n3\n-1\n7\n2\n", encoding="utf-8")

    lines, run, expected = _simulate(
        ROOT / "sva" / "imported_input" / "root_input.yaml",
        "strict",
        SvaStimulusSource(inputs=inputs),
        tmp_path / "out",
    )

    assert expected == [
        "SVA_RESULT child_gets_this_record pass - -",
        "SVA_RESULT parent_gets_this_record pass - -",
        "SVA_RESULT child_and_parent_agree pass - -",
    ]
    _assert_agrees(lines, run, expected, "root input to child")


@needs_icarus
def test_two_instances_of_one_module_match_native(tmp_path):
    # Two imports of the same file are separate instances, in the RTL and
    # in the simulation.
    lines, run, expected = _simulate(
        ROOT / "sva" / "imported_input" / "twins.yaml",
        "strict",
        SvaStimulusSource(steps=4),
        tmp_path / "out",
    )

    assert expected == [
        "SVA_RESULT twins_differ pass - -",
        "SVA_RESULT first_follows_x pass - -",
    ]
    _assert_agrees(lines, run, expected, "two instances of one module")


@needs_icarus
@pytest.mark.parametrize(
    ("model", "results"),
    [
        # c1 reads c0's output from the previous row, in both checkers.
        ("chain.yaml", ["same_step fail - 2", "one_row_later pass - -"]),
        # Imports reading each other: no ordering needed, one step per hop.
        ("loop.yaml", ["in_step pass - -", "counts_rows pass - -"]),
        # Numbers as connections, encoded for the child's port in the RTL.
        ("numbers.yaml", ["integer_copied pass - -", "decimal_copied pass - -"]),
    ],
)
def test_imports_reading_imports_match_native(tmp_path, model, results):
    lines, run, expected = _simulate(
        ROOT / "sva" / "imported_input" / model,
        "strict",
        SvaStimulusSource(steps=3),
        tmp_path / "out",
    )

    assert expected == [f"SVA_RESULT {line}" for line in results]
    _assert_agrees(lines, run, expected, model)


@needs_icarus
@pytest.mark.parametrize("semantics", ["strict", "weak"])
@pytest.mark.parametrize("trace", sorted(p.name for p in MC2_TRACES.glob("*.txt")))
def test_mc2_trace_shapes_as_inputs_match_native(tmp_path, semantics, trace):
    # Each MC2 cross-check trace (columns step, p, t) becomes the input records.
    rows = (MC2_TRACES / trace).read_text(encoding="utf-8").split("\n")[1:]
    records = [line.split()[1:] for line in rows if line.strip()]
    inputs = tmp_path / "inputs.csv"
    inputs.write_text(
        "p,t\n" + "".join(f"{p},{t}\n" for p, t in records), encoding="utf-8"
    )

    lines, run, expected = _simulate(
        FIXTURE / "shapes.yaml",
        semantics,
        SvaStimulusSource(inputs=inputs),
        tmp_path / "out",
    )
    _assert_agrees(lines, run, expected, trace)


@needs_icarus
def test_fixed_point_divergence_is_reported_by_sva_only(tmp_path):
    # The RTL is checked, not the model: overflow and rounding of Q8.8 make
    # SVA fail where native (floating point) passes. Documented, not a bug.
    lines, run, expected = _simulate(
        FIXTURE / "divergence.yaml",
        "strict",
        SvaStimulusSource(steps=8),
        tmp_path / "out",
    )

    assert expected == [
        "SVA_RESULT x_positive pass - -",
        "SVA_RESULT y_tenth_or_one pass - -",
    ]
    assert lines == [
        "SVA_RESULT x_positive fail - 7",
        "SVA_RESULT y_tenth_or_one fail - 1",
    ], run.stdout + run.stderr
    assert run.returncode != 0


@needs_icarus
def test_monitors_compile_without_the_recorder_for_formal(tmp_path):
    # Under FORMAL only the monitor history remains; it must stand on its own.
    # (Icarus does not support bind, so the formal bind file is not compiled.)
    system, cache, import_paths, bound = _load(FIXTURE / "monitors.yaml", "strict")
    transformer = SvaTransformer(
        SvaOptions(),
        _parse_verilog_configs(_collect_import_closure(system), cache, import_paths),
        {system.source_path: bound},
    )
    transformer.write(transformer.generate(system), tmp_path)

    compiled = run_tool(
        IVERILOG,
        [
            "-g2012",
            "-DFORMAL",
            "-o",
            str(tmp_path / "formal.vvp"),
            *map(str, sorted(tmp_path.glob("*.sv"))),
        ],
    )

    assert compiled.returncode == 0, compiled.stdout + compiled.stderr


@needs_verilator
@pytest.mark.parametrize(
    ("model", "semantics", "source"),
    [
        ("monitors.yaml", "strict", "inputs.csv"),
        ("autonomous.yaml", "weak", 20),
        ("shapes.yaml", "weak", None),
    ],
)
def test_verilator_binary_matches_native(tmp_path, model, semantics, source):
    # A few representative runs: each Verilator build compiles C++ (seconds).
    if source is None:  # an MC2 trace shape with overlapping triggers
        rows = (MC2_TRACES / "overlap.txt").read_text(encoding="utf-8").split("\n")[1:]
        inputs = tmp_path / "inputs.csv"
        inputs.write_text(
            "p,t\n"
            + "".join(f"{r.split()[1]},{r.split()[2]}\n" for r in rows if r.strip()),
            encoding="utf-8",
        )
        stimulus = SvaStimulusSource(inputs=inputs)
    elif isinstance(source, int):
        stimulus = SvaStimulusSource(steps=source)
    else:
        stimulus = SvaStimulusSource(inputs=FIXTURE / source)

    lines, run, expected = _simulate(
        FIXTURE / model, semantics, stimulus, tmp_path / "out", VERILATOR_SIM
    )

    _assert_agrees(lines, run, expected, model)


@needs_verilator
def test_verilator_runs_the_supported_concurrent_forms(tmp_path):
    # Verilator 5 runs plain assertions and implications without sequence
    # operators (always, never, zero-bound responses); strong(), ##[a:b],
    # s_eventually and always are unsupported there (see rules.md). Each
    # failing assertion reports `SVA_FAIL <id> row <row>` on every failing
    # row: the first row must be native's reported row, and passing
    # properties must never be reported.
    model = FIXTURE / "concurrent_basic.yaml"
    system, cache, import_paths, bound = _load(model, "strict")
    out = tmp_path / "out"
    transformer = SvaTransformer(
        SvaOptions(style="concurrent"),
        _parse_verilog_configs(_collect_import_closure(system), cache, import_paths),
        {system.source_path: bound},
        SvaStimulusSource(inputs=FIXTURE / "inputs.csv"),
    )
    transformer.write(transformer.generate(system), out)
    top = f"{system.module_config.name}_tb"
    root = os.environ.get(
        "VERILATOR_ROOT", str(Path(VERILATOR).parent.parent / "share" / "verilator")
    )
    compiled = run_tool(
        VERILATOR,
        [
            "--binary",
            "--timing",
            "--assert",
            "-Wno-fatal",
            "--top-module",
            top,
            *sorted(path.name for path in out.glob("*.sv")),
        ],
        env={**_cxx_env(), "VERILATOR_ROOT": root},
        cwd=out,
    )
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    binary = out / "obj_dir" / f"V{top}"
    if not binary.is_file():
        binary = binary.with_suffix(".exe")
    run = run_tool(
        str(binary), ["+verilator+error+limit+100000"], env=_cxx_env(), cwd=out
    )

    first: dict[str, int] = {}
    for line in (run.stdout + run.stderr).splitlines():
        if "SVA_FAIL " in line:
            pid, _, row = line.split("SVA_FAIL ")[1].split()
            first.setdefault(pid, int(row))
    native_system, _, _, _ = _load(model, "strict")
    trace = simulate_inputs(native_system, FIXTURE / "inputs.csv", ",")
    expected = {
        result.id: result.reported_row
        for result in check_properties(bound, native_system, trace, "strict")
        if result.status == "fail"
    }
    assert first == expected, run.stdout + run.stderr
