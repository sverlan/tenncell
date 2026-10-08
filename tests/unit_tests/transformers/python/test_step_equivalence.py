"""Contract: deterministic generated Python steps match the runtime bitwise."""

import random
import struct
from pathlib import Path

import pytest

from nnc.model.system import NncSystem
from nnc.parser.ast.value import FloatValue
from nnc.transformers.python_transformer import PythonTransformer

EQUIVALENCE_ROOT = (
    Path(__file__).resolve().parents[3]
    / "fixtures"
    / "transformers"
    / "python"
    / "equivalence"
)
INPUT_VALUES = [0.0, 0.1, 0.055, 1.0, -2.5]


def _systems(name: str):
    """Return the runtime system and a generated-code instance for one fixture."""
    path = str(EQUIVALENCE_ROOT / name)
    namespace = {"__name__": "generated_equivalence"}
    exec(PythonTransformer().transform(NncSystem.from_yaml(path)), namespace)
    return NncSystem.from_yaml(path), namespace["NncSystem"]()


def _same(left: float, right: float) -> bool:
    """Compare the complete IEEE-754 binary64 representations of two values."""
    return struct.pack("<d", float(left)) == struct.pack("<d", float(right))


def _assert_same_state(runtime: NncSystem, generated, step: int) -> None:
    generated_values = generated.get_variables()
    for name, variable in runtime.variables.items():
        runtime_value = variable.value.value
        generated_value = generated_values[name]
        assert _same(runtime_value, generated_value), (
            f"step {step}: {name} runtime={runtime_value!r} "
            f"generated={generated_value!r}"
        )


def test_bitwise_comparison_distinguishes_nan_payloads():
    first = struct.unpack("<d", bytes.fromhex("010000000000f87f"))[0]
    second = struct.unpack("<d", bytes.fromhex("020000000000f87f"))[0]

    assert first != first
    assert second != second
    assert not _same(first, second)


@pytest.mark.parametrize(
    "fixture",
    [
        "accumulation.yaml",
        "persistence.yaml",
        "guarded_consumption.yaml",
        "fsm_cross_reference.yaml",
        # zero_reset_mode was already correct before the fix; this case guards
        # against regressions in that path.
        "zero_reset.yaml",
    ],
)
def test_generated_step_matches_runtime_on_random_inputs(fixture):
    runtime, generated = _systems(fixture)
    rng = random.Random(42)
    inputs = list(runtime.input_variables)

    for step in range(1, 1001):
        values = {name: rng.choice(INPUT_VALUES) for name in inputs}
        runtime.step(values)
        generated.step(values)
        _assert_same_state(runtime, generated, step)


def test_consumed_infinite_value_is_replaced_not_cancelled():
    runtime, generated = _systems("accumulation.yaml")
    runtime.variables["sum"].value = FloatValue(float("inf"))
    generated.sum = float("inf")

    values = {"a": 1.0, "b": 1.0, "c": 1.0}
    runtime.step(values)
    generated.step(values)

    # `sum` is consumed, so it is reset before its productions are added; the
    # old value must not leak into the result as inf - inf = nan.
    assert generated.get_variables()["sum"] == ((0.0 + 0.7) + 0.3) + 0.11
    _assert_same_state(runtime, generated, 1)


def test_generated_step_matches_runtime_in_chaotic_closed_loop():
    """Tiny output differences must not be able to change discrete feedback.

    The plant is chaotic and scales its update with the controller outputs, so
    any rounding difference grows until the quantized sensor flips. With the
    old ``((x + c1) + c2) - x`` arithmetic, the sensor sequences matched for
    100 steps and first differed at step 101. Only the discrete sensor is
    compared per step here; exact per-step state equality is covered above.
    """
    runtime, generated = _systems("steering.yaml")
    runtime_position = generated_position = 0.3
    flips = 0
    previous_sensor = None

    for step in range(1, 2001):
        runtime_sensor = 0.055 if runtime_position > 0.5 else 0.0
        generated_sensor = 0.055 if generated_position > 0.5 else 0.0
        assert runtime_sensor == generated_sensor, f"sensor differs at step {step}"
        flips += previous_sensor is not None and runtime_sensor != previous_sensor
        previous_sensor = runtime_sensor

        runtime_position = _plant(runtime_position, runtime.step({"s": runtime_sensor}))
        generated_position = _plant(
            generated_position, generated.step({"s": generated_sensor})
        )

    assert _same(runtime_position, generated_position)
    _assert_same_state(runtime, generated, 2000)
    # The loop must really exercise feedback: the sensor switches often.
    assert flips > 500


def _plant(position: float, outputs: dict[str, float]) -> float:
    """Logistic-map plant whose growth rate depends on the controller outputs."""
    left, right = outputs["left"], outputs["right"]
    rate = 3.6 + 0.3 * left / (left + right)
    return rate * position * (1.0 - position)
