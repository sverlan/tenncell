"""Contract tests for the Python transformer backend."""

from pathlib import Path

import pytest

from nnc.model.system import NncSystem
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
        assert "reader = csv.DictReader(sys.stdin, delimiter=args.csv_delimiter)" in result
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

