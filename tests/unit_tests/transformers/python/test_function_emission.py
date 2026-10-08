"""Contract tests for function calls and qualified FSM states in generated Python."""

import struct
from pathlib import Path

import pytest

from nnc.inputs.yaml.errors import YamlLocatedError
from nnc.model.system import NncSystem
from nnc.parser.ast.value.math_functions import MathFunctions
from nnc.transformers.python.expression_emitter import CONSTANT, PYTHON_FUNCTIONS
from nnc.transformers.python_transformer import PythonTransformer

INPUT_ROOT = (
    Path(__file__).resolve().parents[3]
    / "fixtures"
    / "transformers"
    / "python"
    / "input"
)


def _default_functions(monkeypatch) -> dict[str, int | None]:
    """Return the default registry as ``{name: arity}``, without test additions."""
    monkeypatch.setattr(MathFunctions, "_functions", {})
    monkeypatch.setattr(MathFunctions, "_function_arg_counts", {})
    monkeypatch.setattr(MathFunctions, "_default_functions", {})
    monkeypatch.setattr(MathFunctions, "_default_function_arg_counts", {})
    MathFunctions.register_default_functions()
    return dict(MathFunctions._function_arg_counts)


def _generated(system: NncSystem):
    code = PythonTransformer().transform(system)
    namespace = {"__name__": "generated_functions"}
    exec(code, namespace)
    return code, namespace["NncSystem"]()


def _one_rule_model(tmp_path: Path, expression: str) -> Path:
    path = tmp_path / "model.yaml"
    path.write_text(
        "cells:\n  - id: 1\n    contents:\n      - x = 0\n    output: [x]\n"
        f"rules:\n  - x * 0 + {expression} -> x\n",
        encoding="utf-8",
    )
    return path


def _bits(value: float) -> bytes:
    return struct.pack("<d", float(value))


def test_every_default_function_has_a_generated_python_mapping(monkeypatch):
    defaults = _default_functions(monkeypatch)

    assert set(defaults) <= set(PYTHON_FUNCTIONS)


def _call(name: str, arity: int | None) -> str:
    if arity == 0:
        return f"{name}()"
    if arity == 1:
        return f"{name}(0.5)"
    return f"{name}(0.5, 0.25)"


@pytest.mark.parametrize(
    "name",
    sorted(name for name in PYTHON_FUNCTIONS if name != "random"),
)
def test_generated_function_matches_runtime(tmp_path, monkeypatch, name):
    arity = _default_functions(monkeypatch)[name]
    path = _one_rule_model(tmp_path, _call(name, arity))
    runtime = NncSystem.from_yaml(str(path))
    _, generated = _generated(NncSystem.from_yaml(str(path)))

    runtime.step()
    generated.step()

    assert _bits(generated.get_variables()["x"]) == _bits(
        runtime.variables["x"].value.value
    )


def test_constants_are_emitted_without_a_call(tmp_path):
    code, _ = _generated(NncSystem.from_yaml(str(_one_rule_model(tmp_path, "pi()"))))

    assert PYTHON_FUNCTIONS["pi"] == (CONSTANT, "math.pi")
    assert "math.pi" in code and "math.pi()" not in code


def test_random_is_executable_and_imported_only_when_used(tmp_path):
    with_random = NncSystem.from_yaml(str(_one_rule_model(tmp_path, "random()")))
    code, generated = _generated(with_random)
    generated.step()

    assert "import random" in code
    assert "random.random()" in code
    assert 0.0 <= generated.get_variables()["x"] < 1.0

    without_random = NncSystem.from_yaml(str(_one_rule_model(tmp_path, "sin(0.5)")))
    code_without, _ = _generated(without_random)
    assert "import random" not in code_without


def test_custom_function_is_rejected_at_generation_time(tmp_path, monkeypatch):
    monkeypatch.setitem(MathFunctions._functions, "double_it", lambda value: 2 * value)
    monkeypatch.setitem(MathFunctions._function_arg_counts, "double_it", 1)
    path = _one_rule_model(tmp_path, "double_it(0.5)")
    system = NncSystem.from_yaml(str(path))

    with pytest.raises(YamlLocatedError) as error:
        PythonTransformer().transform(system)

    message = str(error.value)
    assert "Function 'double_it' is not available in generated Python code" in message
    assert "(rule: " in message and "double_it" in message
    assert "model.yaml" in message


def test_overridden_default_function_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setitem(MathFunctions._functions, "sin", lambda _value: 42.0)
    path = _one_rule_model(tmp_path, "sin(0.5)")
    system = NncSystem.from_yaml(str(path))

    with pytest.raises(YamlLocatedError) as error:
        PythonTransformer().transform(system)

    message = str(error.value)
    assert "Function 'sin' is not available in generated Python code" in message
    assert "default implementation was overridden" in message
    assert "model.yaml" in message


def test_empty_non_model_document_is_rejected(tmp_path):
    path = tmp_path / "device.header.yaml"
    path.write_text(
        "schema:\n  name: device\n  ports:\n    - name: ready\n"
        "      direction: output\n      width: 1\n",
        encoding="utf-8",
    )
    system = NncSystem.from_yaml(str(path))

    with pytest.raises(YamlLocatedError) as error:
        PythonTransformer().transform(system)

    assert "nothing to generate" in str(error.value)
    assert "device.header.yaml" in str(error.value)


def test_composed_child_with_random_math_and_fsm_state_runs():
    system = NncSystem.from_yaml(str(INPUT_ROOT / "composed_functions_root.yaml"))
    code, generated = _generated(system)
    runtime = NncSystem.from_yaml(str(INPUT_ROOT / "composed_functions_root.yaml"))

    assert "import random" in code
    for start in (0.0, 1.0, 0.0, 0.0):
        # `level` does not depend on random(), so outputs stay comparable.
        assert generated.step({"start": start}) == runtime.step({"start": start})
