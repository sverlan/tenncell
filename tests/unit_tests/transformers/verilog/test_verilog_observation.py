"""Contract tests for VerilogTransformer.observe (the shared observation API).

The observation names every TENNCell value as the generated RTL declares it, so
a checker connected to those signals reads exactly what the module computes.
"""

import dataclasses
import re
from pathlib import Path

import pytest

from nnc.cli_transform import _collect_import_closure, _parse_verilog_configs
from nnc.model.system import NncSystem
from nnc.transformers import VerilogTransformer
from nnc.transformers.verilog import (
    ObservedSignal,
    ObservedSignalKind,
    VerilogObservation,
)
from nnc.transformers.verilog.generation.observation import (
    BINDING_WIRE,
    IMPORT_INPUT,
    IMPORT_WIRE,
    INPUT_PORT,
    STATE,
)

FIXTURE_ROOT = (
    Path(__file__).resolve().parents[3] / "fixtures" / "transformers" / "verilog"
)
INPUT_ROOT = FIXTURE_ROOT / "input"

EXPECTED_ROOT = FIXTURE_ROOT / "expected"

# Every model with a Verilog golden file (root and imported modules): the golden
# `expected/<path>.sv` belongs to the model `input/<path>.yaml`.
GOLDENS = sorted(EXPECTED_ROOT.rglob("*.sv"))
MODELS = [
    golden.relative_to(EXPECTED_ROOT).with_suffix(".yaml").as_posix()
    for golden in GOLDENS
]


def test_every_golden_file_has_a_model():
    # Guards the derived MODELS list: a golden without a model would be skipped.
    missing = [model for model in MODELS if not (INPUT_ROOT / model).is_file()]

    assert missing == []
    assert len(MODELS) >= 19


_DECLARATION = re.compile(
    r"^\s*(?:input |output )?logic(?P<signed> signed)?"
    r"(?: \[(?P<msb>\d+):0\])? (?P<name>[A-Za-z_]\w*)\s*[,;]?\s*$"
)


def _load(model: str) -> tuple[NncSystem, VerilogTransformer]:
    path = INPUT_ROOT / model
    import_paths = [str(path.parent)]
    raw_data_cache: dict = {}
    system = NncSystem.from_yaml(
        str(path), import_paths=import_paths, _raw_data_cache=raw_data_cache
    )
    transformer = VerilogTransformer(
        _parse_verilog_configs(
            _collect_import_closure(system), raw_data_cache, import_paths
        )
    )
    return system, transformer


def _declarations(rtl: str) -> dict[str, tuple[int, bool]]:
    """Map each declared signal name to (width, signed)."""
    found = {}
    for line in rtl.splitlines():
        match = _DECLARATION.match(line)
        if match:
            width = int(match["msb"]) + 1 if match["msb"] is not None else 1
            found[match["name"]] = (width, match["signed"] is not None)
    return found


@pytest.mark.parametrize("model", MODELS)
def test_every_root_variable_and_imported_port_is_observed(model):
    system, transformer = _load(model)
    expected = set(system.variables)
    for item in system.imports:
        expected |= {f"{item.alias}.{name}" for name in item.system.input_variables}
        expected |= {f"{item.alias}.{name}" for name in item.system.output_variables}

    assert set(transformer.observe(system).signals) == expected


@pytest.mark.parametrize("model", MODELS)
def test_connectable_signals_match_their_rtl_declarations(model):
    # Checked against the RTL that transform() emits; byte-identity with the
    # golden files is owned by test_verilog_transformer.py.
    system, transformer = _load(model)
    declared = _declarations(transformer.transform(system))

    observation = transformer.observe(system)

    assert observation.signals, model
    for signal in observation.signals.values():
        if not signal.connectable:
            continue
        assert signal.expression in declared, signal
        assert declared[signal.expression] == (signal.width, signal.signed), signal


@pytest.mark.parametrize("model", MODELS)
def test_observing_does_not_change_the_rtl(model):
    system, fresh = _load(model)
    expected = fresh.transform(system)
    _, transformer = _load(model)

    transformer.observe(system)
    rtl = transformer.transform(system)
    transformer.observe(system)

    assert rtl == expected
    assert transformer.transform(system) == rtl


def _summary(signal: ObservedSignal) -> tuple:
    return (
        signal.expression,
        signal.kind,
        signal.encoding_kind,
        signal.width,
        signal.signed,
        signal.frac_bits,
        signal.connectable,
    )


def test_renamed_input_port_is_observed_under_its_verilog_name():
    system, transformer = _load("renamed_ports.yaml")

    observation = transformer.observe(system)

    assert (observation.module_name, observation.clock, observation.reset) == (
        "renamed_ports",
        "clk",
        "rst",
    )
    assert observation.reset_active_high
    assert _summary(observation.signal("a")) == (
        "a_in",
        INPUT_PORT,
        "fixed",
        16,
        True,
        8,
        True,
    )
    assert _summary(observation.signal("x")) == (
        "state_x",
        STATE,
        "fixed",
        16,
        True,
        8,
        True,
    )


def test_imported_ports_are_observed_in_the_parent():
    system, transformer = _load("renamed_import/parent.yaml")

    observation = transformer.observe(system)

    # The child's output is the parent's wire; its input is what the parent
    # drives into it (here the parent's input port `u`).
    assert _summary(observation.signal("c0.y")) == (
        "c0__y",
        IMPORT_WIRE,
        "fixed",
        16,
        True,
        8,
        True,
    )
    assert _summary(observation.signal("c0.a")) == (
        "u",
        IMPORT_INPUT,
        "fixed",
        16,
        True,
        8,
        True,
    )
    assert observation.signal("c0.a").initial_value == 0


def test_binding_wires_and_converted_import_inputs():
    system, transformer = _load("helper_generated_literals/root.yaml")

    observation = transformer.observe(system)

    # A converted connection is an expression, not a declared signal.
    child_input = observation.signal("child0.sig")
    assert child_input.kind == IMPORT_INPUT
    assert child_input.expression == "conv_logic_to_logic_32(led)"
    assert not child_input.connectable

    system, transformer = _load("external_output_wire/root.yaml")
    assert transformer.observe(system).signal("uart_ready").kind == BINDING_WIRE


def test_signed_logic_storage_is_observed_as_declared_signed():
    # `alarm` has a signed 32-bit logic port, and its register is declared
    # signed too (`logic signed [31:0] state_alarm`).
    system, transformer = _load("imports_externals/controller.yaml")

    alarm = transformer.observe(system).signal("alarm")

    assert _summary(alarm) == ("state_alarm", STATE, "logic", 32, True, 0, True)


def test_observation_is_read_only():
    system, transformer = _load("simple.yaml")
    observation = transformer.observe(system)

    # The public types are exported from nnc.transformers.verilog.
    assert isinstance(observation, VerilogObservation)
    assert isinstance(observation.signal("x"), ObservedSignal)
    assert observation.signal("x").kind in ObservedSignalKind.__args__

    with pytest.raises(TypeError):
        observation.signals["y"] = observation.signal("x")  # type: ignore[index]
    with pytest.raises(dataclasses.FrozenInstanceError):
        observation.signal("x").width = 8  # type: ignore[misc]
    with pytest.raises(KeyError, match="'nope' is not observable in module"):
        observation.signal("nope")
