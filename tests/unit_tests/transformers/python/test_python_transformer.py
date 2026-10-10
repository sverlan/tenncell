"""Contract tests for the Python transformer backend."""

from pathlib import Path

import pytest

from nnc.model.system import NncSystem
from nnc.parser.ast.value.math_functions import MathFunctions
from nnc.transformers.python.expression_emitter import CALL, PYTHON_FUNCTIONS
from nnc.transformers.python_transformer import PythonTransformer


FIXTURE_ROOT = (
    Path(__file__).resolve().parents[3] / "fixtures" / "transformers" / "python"
)
INPUT_ROOT = FIXTURE_ROOT / "input"
EXPECTED_ROOT = FIXTURE_ROOT / "expected"


def load_system(name: str, import_paths: list[str] | None = None) -> NncSystem:
    return NncSystem.from_yaml(str(INPUT_ROOT / name), import_paths=import_paths or [])


def read_fixture(name: str) -> str:
    return (EXPECTED_ROOT / name).read_text(encoding="utf-8")


def normalize_output(text: str) -> str:
    return text if text.endswith("\n") else text + "\n"


def assert_matches_fixture(
    system_name: str, expected_name: str, import_paths: list[str] | None = None
) -> str:
    transformer = PythonTransformer()
    system = load_system(system_name, import_paths=import_paths)
    result = normalize_output(transformer.transform(system))
    expected = normalize_output(read_fixture(expected_name))
    assert result == expected
    return result


class TestPythonTransformer:
    def test_get_file_extension(self):
        transformer = PythonTransformer()
        assert transformer.get_file_extension() == ".py"

    def test_transform_generates_basic_module_from_real_fixture(self):
        assert_matches_fixture("basic.yaml", "basic.py")

    def test_transform_generates_csv_processing_for_inputs(self):
        result = assert_matches_fixture("csv_with_input.yaml", "csv_with_input.py")
        assert "import csv" in result
        assert (
            "reader = csv.DictReader(sys.stdin, delimiter=args.csv_delimiter)" in result
        )
        assert "parser.add_argument('--csv-include-initial'" in result
        assert "parser.add_argument('--csv-delimiter'" in result
        assert "required_inputs = ['input_x']" in result
        assert "inputs['input_x'] = float(input_row['input_x'])" in result
        assert "output = system.step(inputs)" in result
        assert "fieldnames = ['step'] + ['out']" in result

    def test_transform_generates_csv_processing_without_inputs(self):
        result = assert_matches_fixture(
            "csv_without_input.yaml", "csv_without_input.py"
        )
        assert (
            "parser.add_argument('steps', type=int, help='Number of steps to execute')"
            in result
        )
        assert "for step_num in range(args.steps):" in result
        assert "output = system.step()" in result
        assert "fieldnames = ['step'] + ['out']" in result
        assert "parser.add_argument('--csv-no-initial'" in result
        assert "step0_row = {'step': 0}" in result

    def test_transform_generates_all_variables_output_without_outputs(self):
        result = assert_matches_fixture("no_outputs.yaml", "no_outputs.py")
        assert "# No output variables defined, return all variables" in result
        assert "return self.get_variables()" in result
        assert "fieldnames = ['step'] + list(all_vars.keys())" in result

    def test_transform_composed_system_emits_single_public_wrapper(self):
        result = assert_matches_fixture(
            "composed_root.yaml", "composed_root.py", [str(INPUT_ROOT)]
        )
        assert "class _Module_sensor(_NncModuleBase):" in result
        assert "class _Module_controller(_NncModuleBase):" in result
        assert "class NncSystem(_Module_controller):" in result
        assert result.count("class NncSystem(") == 1
        assert "self._import_sensor0 = _Module_sensor()" in result

    def test_transform_composed_system_executes_like_runtime(self):
        runtime_system = load_system("composed_root.yaml", [str(INPUT_ROOT)])
        generated_code = PythonTransformer().transform(runtime_system)

        namespace = {"__name__": "generated_test"}
        exec(generated_code, namespace)
        generated_system = namespace["NncSystem"]()

        runtime_output = runtime_system.step({"sample": 2.0})
        generated_output = generated_system.step({"sample": 2.0})

        assert generated_output == runtime_output

    def test_numbers_as_connections_step_like_runtime(self):
        fixtures = FIXTURE_ROOT.parents[1] / "verification" / "sva" / "imported_input"
        runtime_system = NncSystem.from_yaml(
            str(fixtures / "numbers.yaml"), import_paths=[str(fixtures)]
        )
        namespace = {"__name__": "generated_test"}
        exec(PythonTransformer().transform(runtime_system), namespace)
        generated_system = namespace["NncSystem"]()

        runtime_system.step()
        generated_system.step()

        assert [generated_system._import_c0.y, generated_system._import_c1.y] == [
            5.0,
            -2.5,
        ]

    @pytest.mark.parametrize("model", ["chain.yaml", "loop.yaml"])
    def test_imports_reading_imports_step_like_runtime(self, model):
        # Every import reads the configuration before the step: a chained
        # import lags one step; a loop of imports needs no ordering.
        fixtures = FIXTURE_ROOT.parents[1] / "verification" / "sva" / "imported_input"
        runtime_system = NncSystem.from_yaml(
            str(fixtures / model), import_paths=[str(fixtures)]
        )
        namespace = {"__name__": "generated_test"}
        exec(PythonTransformer().transform(runtime_system), namespace)
        generated_system = namespace["NncSystem"]()
        children = {item.alias: item.system for item in runtime_system.imports}

        runtime_rows, generated_rows = [], []
        for _ in range(4):
            runtime_system.step()
            generated_system.step()
            runtime_rows.append(
                [children[a].variables["y"].value.value for a in ("c0", "c1")]
            )
            generated_rows.append(
                [getattr(generated_system, f"_import_{a}").y for a in ("c0", "c1")]
            )

        assert generated_rows == runtime_rows
        if model == "chain.yaml":
            assert runtime_rows == [[0.0, 0.0], [1.0, 0.0], [2.0, 1.0], [3.0, 2.0]]
        else:
            assert runtime_rows == [[1.0, 1.0], [2.0, 2.0], [3.0, 3.0], [4.0, 4.0]]

    def test_generated_step_matches_runtime_floating_point_semantics(self):
        runtime_system = load_system("numerical_semantics.yaml")
        generated_code = assert_matches_fixture(
            "numerical_semantics.yaml", "numerical_semantics.py"
        )

        namespace = {"__name__": "generated_test"}
        exec(generated_code, namespace)
        generated_system = namespace["NncSystem"]()

        runtime_output = runtime_system.step({"sensor": 1.0})
        generated_output = generated_system.step({"sensor": 1.0})

        assert generated_output == runtime_output
        assert generated_output["rounded"].hex() == (0.055).hex()
        assert generated_output["extreme"] == 1.0

    def test_generated_step_matches_runtime_in_feedback_loop(self):
        runtime_system = load_system("numerical_semantics.yaml")
        generated_code = PythonTransformer().transform(runtime_system)

        namespace = {"__name__": "generated_test"}
        exec(generated_code, namespace)
        generated_system = namespace["NncSystem"]()
        runtime_sensor = generated_sensor = 1.0
        threshold = 0.05500000000000001

        for _ in range(1000):
            runtime_output = runtime_system.step({"sensor": runtime_sensor})
            generated_output = generated_system.step({"sensor": generated_sensor})
            assert generated_output == runtime_output
            runtime_sensor = float(runtime_output["motor"] >= threshold)
            generated_sensor = float(generated_output["motor"] >= threshold)
            assert generated_sensor == runtime_sensor

    def test_generated_step_preserves_rule_evaluation_order(self, monkeypatch):
        calls: list[str] = []

        def record(name: str, result: float):
            def function(_value: float) -> float:
                calls.append(name)
                return result

            return function

        functions = {
            "guard0": record("guard0", 1.0),
            "producer0": record("producer0", 0.1),
            "guard1": record("guard1", 1.0),
            "producer1": record("producer1", 0.2),
        }
        for name, function in functions.items():
            monkeypatch.setitem(MathFunctions._functions, name, function)
            monkeypatch.setitem(MathFunctions._function_arg_counts, name, 1)
            # Custom functions are rejected by generated Python; this test maps
            # them explicitly as test-only defaults and supplies them in the
            # exec namespace below.
            monkeypatch.setitem(MathFunctions._default_functions, name, function)
            monkeypatch.setitem(MathFunctions._default_function_arg_counts, name, 1)
            monkeypatch.setitem(PYTHON_FUNCTIONS, name, (CALL, name))

        runtime_system = load_system("evaluation_order.yaml")
        generated_code = PythonTransformer().transform(runtime_system)
        namespace = {"__name__": "generated_test", **functions}
        exec(generated_code, namespace)
        generated_system = namespace["NncSystem"]()

        runtime_output = runtime_system.step()
        runtime_calls = calls.copy()
        calls.clear()
        generated_output = generated_system.step()

        expected_calls = ["guard0", "producer0", "guard1", "producer1"]
        assert runtime_calls == expected_calls
        assert calls == expected_calls
        assert generated_output == runtime_output

    def test_transform_zero_reset_mode_omits_used_vars(self):
        result = assert_matches_fixture("zero_reset.yaml", "zero_reset.py")
        assert "used_vars = set()" not in result
        assert "trigger_new = self.trigger" in result
        assert "out_new = 0.0" in result
        assert "trigger_new -= self.trigger" not in result

    def test_transform_zero_reset_mode_preserves_input_variables(self):
        result = assert_matches_fixture("zero_reset.yaml", "zero_reset.py")
        assert "trigger_new = self.trigger" in result
        assert "out_new = 0.0" in result
