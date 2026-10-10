"""Contract tests for replaying a SymbiYosys witness as SVA stimulus."""

import json
from pathlib import Path

import pytest

from nnc.cli_transform import (
    _collect_import_closure,
    _parse_verification_configs,
    _parse_verilog_configs,
)
from nnc.model.system import NncSystem
from nnc.transformers import SvaTransformer
from nnc.verification.generic_properties.native import VerificationError
from nnc.verification.sva import SvaOptions
from nnc.verification.sva_replay import WitnessPort, read_witness
from nnc.verification.sva_stimulus import SvaStimulusSource

SVA = Path(__file__).resolve().parents[2] / "fixtures" / "verification" / "sva"
# Witness of `bmc` on formal/follow.yaml keeping input_never_max (never u == 5):
# step 0 is the reset step, step 1 gives u_in = 5.0 (0x0500), and the
# violation on row 1 is reported at step 3.
WITNESS = SVA / "replay" / "follow_never_max.yw"
U_IN = WitnessPort("u_in", 16, True)


def _generate(model: Path, witness: Path):
    cache: dict = {}
    import_paths = [str(model.parent)]
    system = NncSystem.from_yaml(
        str(model), import_paths=import_paths, _raw_data_cache=cache
    )
    transformer = SvaTransformer(
        SvaOptions(),
        _parse_verilog_configs(_collect_import_closure(system), cache, import_paths),
        _parse_verification_configs([system], cache),
        SvaStimulusSource(witness=witness),
    )
    return transformer.generate(system)


def _edited(tmp_path: Path, change) -> Path:
    data = json.loads(WITNESS.read_text(encoding="utf-8"))
    change(data)
    path = tmp_path / "edited.yw"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_witness_rows_and_records():
    replay = read_witness(WITNESS, [U_IN], "rst", True)

    assert replay.rows == 1
    assert replay.records == ({"u_in": 1280},)


def test_signed_values_are_twos_complement(tmp_path):
    def negative(data):  # u_in = -3.0 = -768 = 0xfd00 at step 1
        data["steps"][1]["bits"] = "1111110100000000" + "00"

    replay = read_witness(_edited(tmp_path, negative), [U_IN], "rst", True)

    assert replay.records == ({"u_in": -768},)


def test_replay_writes_stimulus_and_names_the_witness_row():
    output = _generate(SVA / "formal" / "follow.yaml", WITNESS)

    hex_lines = output.files["follow_inputs.hex"].splitlines()
    assert hex_lines[1] == (
        "// replay of follow_never_max.yw: rows 0..1; expected: a property first "
        "fails, or a cover is first hit, on row 1 (the witness is matched to the "
        "model by its ports only)"
    )
    assert hex_lines[3:] == ["0500"]
    assert output.files["follow_inputs_decoded.csv"] == "u\n5.0\n"
    testbench = output.files["follow_tb.sv"]
    assert hex_lines[1] in testbench
    # Self-checking: success means the witness's failure comes back on row 1.
    assert "sva_checker.sva_replay_check(64'd1, sva_reproduced);" in testbench
    assert "SVA_REPLAY reproduced on row 1" in testbench
    assert "SVA: a generic property failed" not in testbench
    checker = output.files["follow_sva.sv"]
    assert "task automatic sva_replay_check(" in checker


@pytest.mark.parametrize(
    ("options", "raw_only"),
    [(SvaOptions(style="concurrent"), False), (SvaOptions(), True)],
)
def test_replay_needs_the_monitor_checker_and_generic_properties(
    tmp_path, options, raw_only
):
    # Concurrent style has no recorder, and a raw-only checker no property to
    # check: neither can tell whether the witness is reproduced.
    path = SVA / "formal" / "follow.yaml"
    if raw_only:
        path = tmp_path / "raw.yaml"
        path.write_text(
            "cells:\n  - id: 1\n    contents:\n      - u = 0\n    input: [u]\n"
            "verilog:\n  real_encoding: {kind: fixed_point, signed: true, width: 16, "
            "frac_bits: 8}\n  ports:\n    u: {direction: input, kind: fixed, "
            "width: 16, signed: true, rename: u_in}\n"
            "verification:\n  backends:\n    sva:\n      raw:\n        - id: r\n"
            '          code: "// ${u}"\n',
            encoding="utf-8",
        )
    cache: dict = {}
    system = NncSystem.from_yaml(
        str(path), import_paths=[str(path.parent)], _raw_data_cache=cache
    )
    transformer = SvaTransformer(
        options,
        _parse_verilog_configs(
            _collect_import_closure(system), cache, [str(path.parent)]
        ),
        _parse_verification_configs([system], cache),
        SvaStimulusSource(witness=WITNESS),
    )

    with pytest.raises(
        ValueError, match="needs the monitor style and generic properties"
    ):
        transformer.generate(system)


def test_model_without_inputs_replays_the_number_of_rows():
    # The counter fixture has no input: only the length of the witness counts.
    output = _generate(SVA / "formal" / "counter.yaml", WITNESS)

    assert "localparam int RECORDS = 1;" in output.files["counter_tb.sv"]
    assert "counter_inputs.hex" not in output.files


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda d: d.update(format="VCD"), "not a Yosys witness trace"),
        (lambda d: d.update(steps=d["steps"][:2]), "has 2 steps"),
        # Reset inactive at step 0: an induction trace, not from the reset.
        (
            lambda d: d["steps"][0].update(bits=d["steps"][0]["bits"][:-2] + "00"),
            "does not start from the reset",
        ),
        # Reset asserted again after step 0.
        (
            lambda d: d["steps"][2].update(bits=d["steps"][2]["bits"][:-2] + "10"),
            "does not start from the reset",
        ),
        (
            lambda d: d["steps"][1].update(bits=d["steps"][1]["bits"][:-2] + "x0"),
            "the reset is unknown at step 1",
        ),
        (
            lambda d: d["steps"][1].update(bits="0101"),
            "step 1 of the witness should have 18 bits",
        ),
        (
            lambda d: d["steps"][1].update(bits="2" * 18),
            "step 1 of the witness has bits other than 0, 1, x, \\?",
        ),
        (lambda d: d["signals"].append({"width": 2}), "malformed witness signal"),
        (lambda d: d["signals"][0].update(path=[7]), "malformed witness signal"),
        (lambda d: d["signals"][0].update(path=[]), "malformed witness signal"),
        (lambda d: d["signals"][0].update(width=True), "malformed witness signal"),
        (lambda d: d["signals"][0].update(width=1.9), "malformed witness signal"),
        (lambda d: d["signals"][0].update(offset=-1), "malformed witness signal"),
        (
            lambda d: d["signals"][0].update(init_only="false"),
            "malformed witness signal",
        ),
        (lambda d: d["signals"].append(7), "malformed witness signal"),
    ],
)
def test_bad_witnesses_are_rejected(tmp_path, change, message):
    with pytest.raises(VerificationError, match=message):
        read_witness(_edited(tmp_path, change), [U_IN], "rst", True)


def test_a_port_missing_from_the_witness_is_rejected():
    with pytest.raises(VerificationError, match="has no signal 'v_in'"):
        read_witness(WITNESS, [WitnessPort("v_in", 16, True)], "rst", True)


def test_active_low_reset(tmp_path):
    def invert_reset(data):  # reset bit (second from the end) 1 -> 0 and 0 -> 1
        for step in data["steps"]:
            bits = step["bits"]
            step["bits"] = bits[:-2] + ("0" if bits[-2] == "1" else "1") + bits[-1]

    witness = _edited(tmp_path, invert_reset)

    assert read_witness(witness, [U_IN], "rst", False).records == ({"u_in": 1280},)
    with pytest.raises(VerificationError, match="does not start from the reset"):
        read_witness(witness, [U_IN], "rst", True)


def test_unknown_input_bits_are_replayed_as_zero(tmp_path):
    def unknown(data):  # u_in = x00000101 xxxxxxxx: unknown bits become 0
        data["steps"][1]["bits"] = "x0000101" + "xxxxxxxx" + "00"

    replay = read_witness(_edited(tmp_path, unknown), [U_IN], "rst", True)

    assert replay.records == ({"u_in": 1280},)


def test_ports_split_into_fragments_are_assembled_by_offset(tmp_path):
    # u_in in two 8-bit fragments (offsets 0 and 8) with an init-only signal
    # between them; the fragments are stored from the last listed to the first.
    witness = tmp_path / "split.yw"
    signals = [
        {"path": ["\\clk"], "width": 1, "offset": 0, "init_only": False},
        {"path": ["\\rst"], "width": 1, "offset": 0, "init_only": False},
        {"path": ["\\u_in"], "width": 8, "offset": 0, "init_only": False},
        {
            "path": ["\\_witness_", "\\anyinit"],
            "width": 4,
            "offset": 0,
            "init_only": True,
        },
        {"path": ["\\u_in"], "width": 8, "offset": 8, "init_only": False},
    ]
    steps = [
        {"bits": "00000000" + "0000" + "00000000" + "1" + "0"},  # reset
        {"bits": "00000101" + "00000001" + "0" + "0"},  # u_in = 0x0501
        {"bits": "0" * 18},
        {"bits": "0" * 18},
    ]
    witness.write_text(
        json.dumps(
            {"format": "Yosys Witness Trace", "signals": signals, "steps": steps}
        ),
        encoding="utf-8",
    )

    assert read_witness(witness, [U_IN], "rst", True).records == ({"u_in": 0x0501},)
