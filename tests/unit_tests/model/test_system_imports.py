"""Tests for extended YAML loading and import resolution."""

from pathlib import Path
import textwrap
import shutil
import uuid

import pytest

from nnc.parser import parse_expression
from nnc.model.system import NncSystem
from nnc.parser.ast import ReferenceExpression


def write_text(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


class TempDirContext:
    def __init__(self):
        self.path = (
            Path(r"C:\Users\ver\.codex\memories\nump_test_tmp")
            / f"tmp_{uuid.uuid4().hex}"
        )

    def __enter__(self):
        self.path.mkdir(parents=True, exist_ok=False)
        return str(self.path)

    def __exit__(self, exc_type, exc, tb):
        shutil.rmtree(self.path, ignore_errors=True)


class TestSystemImports:
    def test_loads_defaults_for_legacy_yaml(self):
        with TempDirContext() as tmp_dir:
            system_file = Path(tmp_dir) / "legacy.yaml"
            write_text(
                system_file,
                """
                cells:
                  - id: 1
                    contents:
                      - x = 0
                      - y = 1
                    input: [x]
                    output: [y]
                rules:
                  - x + 1 -> y
                """,
            )

            system = NncSystem.from_yaml(str(system_file))

            assert system.module_config.name == "legacy"
            assert not hasattr(system, "verilog_config")
            assert system.module_config.zero_reset_mode is False
            assert system.imports == []

    def test_resolves_imports_headers_aliases_and_search_paths(self):
        with TempDirContext() as tmp_dir:
            tmp_path = Path(tmp_dir)
            lib_dir = tmp_path / "lib"
            root_file = tmp_path / "controller.yaml"
            write_text(
                lib_dir / "sensor.yaml",
                """
                module:
                  name: sensor
                cells:
                  - id: 1
                    contents:
                      - level = 2
                    output: [level]
                rules: []
                """,
            )
            write_text(
                root_file,
                """
                module:
                  name: controller_top
                imports:
                  - module: sensor.yaml
                    as: sensor0
                aliases:
                  sensed: sensor0.level
                constants:
                  THRESHOLD: 5
                cells:
                  - id: 1
                    contents:
                      - alarm = 0
                    output: [alarm]
                rules:
                  - sensed > THRESHOLD | 1 -> alarm
                """,
            )

            system = NncSystem.from_yaml(str(root_file), import_paths=[str(lib_dir)])

            assert system.module_config.name == "controller_top"
            assert system.imports[0].alias == "sensor0"
            assert "sensed" in system.aliases
            assert isinstance(system.aliases["sensed"], ReferenceExpression)

    def test_parse_expression_supports_qualified_references(self):
        expr = parse_expression("mod0.value + sensor0.input_x", {})
        assert str(expr) == "(mod0.value + sensor0.input_x)"

    def test_constants_support_ordered_expression_evaluation(self):
        with TempDirContext() as tmp_dir:
            system_file = Path(tmp_dir) / "constant_expr.yaml"
            write_text(
                system_file,
                """
                constants:
                  A: 2 * 5
                  B: 3 * A + 1
                  C: "(B - A) / 3"
                cells:
                  - id: 1
                    contents:
                      - x = 0
                    output: [x]
                rules:
                  - C -> x
                """,
            )

            system = NncSystem.from_yaml(str(system_file))

            assert system.constants["A"].value == 10.0
            assert system.constants["B"].value == 31.0
            assert system.constants["C"].value == 7.0
            assert system.step() == {"x": 7.0}

    def test_constant_expressions_must_reference_previous_constants(self):
        with TempDirContext() as tmp_dir:
            system_file = Path(tmp_dir) / "bad_constant_expr.yaml"
            write_text(
                system_file,
                """
                constants:
                  B: A + 1
                  A: 2
                cells:
                  - id: 1
                    contents:
                      - x = 0
                rules: []
                """,
            )

            with pytest.raises(ValueError, match="Error evaluating constant 'B'"):
                NncSystem.from_yaml(str(system_file))

    def test_import_cycle_is_rejected(self):
        with TempDirContext() as tmp_dir:
            a_file = Path(tmp_dir) / "a.yaml"
            b_file = Path(tmp_dir) / "b.yaml"
            write_text(
                a_file,
                """
                imports:
                  - module: b.yaml
                    as: b0
                cells:
                  - id: 1
                    contents:
                      - x = 0
                rules: []
                """,
            )
            write_text(
                b_file,
                """
                imports:
                  - module: a.yaml
                    as: a0
                cells:
                  - id: 1
                    contents:
                      - y = 0
                rules: []
                """,
            )

            with pytest.raises(ValueError, match="Import cycle detected"):
                NncSystem.from_yaml(str(a_file))

    def test_runtime_step_supports_imported_modules(self):
        with TempDirContext() as tmp_dir:
            tmp_path = Path(tmp_dir)
            lib_dir = tmp_path / "lib"
            root_file = tmp_path / "controller.yaml"
            write_text(
                lib_dir / "sensor.yaml",
                """
                module:
                  name: sensor
                cells:
                  - id: 1
                    contents:
                      - raw = 0
                      - level = 0
                    input: [raw]
                    output: [level]
                rules:
                  - raw + 1 -> level
                """,
            )
            write_text(
                root_file,
                """
                module:
                  name: controller
                imports:
                  - module: sensor.yaml
                    as: sensor0
                    connections:
                      raw: sample
                cells:
                  - id: 1
                    contents:
                      - sample = 0
                      - alarm = 0
                    input: [sample]
                    output: [alarm]
                rules:
                  - sensor0.level > 2 | sensor0.level -> alarm
                """,
            )

            system = NncSystem.from_yaml(str(root_file), import_paths=[str(lib_dir)])
            output = system.step({"sample": 2.0})

            assert output == {"alarm": 3.0}
            assert system.imports[0].system.variables["level"].value.value == 3.0

    def test_runtime_zero_reset_mode_recomputes_all_local_variables(self):
        with TempDirContext() as tmp_dir:
            system_file = Path(tmp_dir) / "zero_reset.yaml"
            write_text(
                system_file,
                """
                module:
                  name: zero_reset_demo
                  zero_reset_mode: true
                cells:
                  - id: 1
                    contents:
                      - x = 5
                      - y = 0
                    output: [y]
                rules:
                  - x + 1 -> y
                """,
            )

            system = NncSystem.from_yaml(str(system_file))
            output = system.step()

            assert output == {"y": 6.0}
            assert system.variables["x"].value.value == 0.0
            assert system.variables["y"].value.value == 6.0

    def test_runtime_zero_reset_mode_preserves_current_inputs(self):
        with TempDirContext() as tmp_dir:
            system_file = Path(tmp_dir) / "zero_reset_inputs.yaml"
            write_text(
                system_file,
                """
                module:
                  name: zero_reset_inputs
                  zero_reset_mode: true
                cells:
                  - id: 1
                    contents:
                      - trigger = 0
                      - out = 0
                    input: [trigger]
                    output: [out]
                rules:
                  - trigger + 1 -> out
                """,
            )

            system = NncSystem.from_yaml(str(system_file))
            output = system.step({"trigger": 2.0})

            assert output == {"out": 3.0}
            assert system.variables["trigger"].value.value == 2.0
            assert system.variables["out"].value.value == 3.0

    def test_recursive_if_then_else_lowers_and_runs(self):
        with TempDirContext() as tmp_dir:
            system_file = Path(tmp_dir) / "if_recursive.yaml"
            write_text(
                system_file,
                """
                module:
                  name: if_recursive_demo
                  zero_reset_mode: true
                cells:
                  - id: 1
                    contents:
                      - x = 0
                      - y = 0
                      - z = 0
                    input: [x]
                    output: [y, z]
                rules:
                  - if: x > 2
                    then:
                      - 1 -> y
                      - if: x > 10
                        then: 2 -> z
                        else: 1 -> z
                    else:
                      - 0 -> y
                      - 0 -> z
                """,
            )

            system = NncSystem.from_yaml(str(system_file))
            assert system.step({"x": 1.0}) == {"y": 0.0, "z": 0.0}
            assert system.step({"x": 5.0}) == {"y": 1.0, "z": 1.0}
            assert system.step({"x": 11.0}) == {"y": 1.0, "z": 2.0}

    def test_fsm_counter_lowers_and_runs(self):
        with TempDirContext() as tmp_dir:
            system_file = Path(tmp_dir) / "fsm_counter.yaml"
            write_text(
                system_file,
                """
                constants:
                  MAX_COUNT: 2
                cells:
                  - id: 1
                    contents:
                      - ctrl_state = 0
                      - counter = 0
                      - start = 0
                      - done = 0
                    input: [start]
                    output: [counter, done]
                fsm:
                  - name: ctrl
                    variable: ctrl_state
                    initial: IDLE
                    states:
                      - IDLE:
                          rules:
                            - if: start > 0
                              then:
                                - RUN -> ctrl_state
                                - counter * 0 -> counter
                                - done * 0 -> done
                      - RUN:
                          rules:
                            - if: counter >= MAX_COUNT
                              then:
                                - DONE -> ctrl_state
                                - 1 -> done
                              else:
                                - counter + 1 -> counter
                      - DONE:
                          rules:
                            - done -> done
                """,
            )

            system = NncSystem.from_yaml(str(system_file))
            assert system.step({"start": 1.0}) == {"counter": 0.0, "done": 0.0}
            assert system.step({"start": 0.0}) == {"counter": 1.0, "done": 0.0}
            assert system.step({"start": 0.0}) == {"counter": 2.0, "done": 0.0}
            assert system.step({"start": 0.0}) == {"counter": 2.0, "done": 1.0}
            assert system.constants["ctrl__IDLE"].value == 0.0
            assert system.constants["ctrl__RUN"].value == 1.0
            assert system.constants["ctrl__DONE"].value == 2.0

    def test_multiple_fsms_are_supported(self):
        with TempDirContext() as tmp_dir:
            system_file = Path(tmp_dir) / "dual_fsm.yaml"
            write_text(
                system_file,
                """
                cells:
                  - id: 1
                    contents:
                      - ctrl_state = 0
                      - pulse_state = 0
                      - start = 0
                      - stop = 0
                      - led = 0
                    input: [start, stop]
                    output: [led]
                fsm:
                  - name: ctrl
                    variable: ctrl_state
                    initial: IDLE
                    states:
                      - IDLE:
                          rules:
                            - if: start > 0
                              then: ACTIVE -> ctrl_state
                      - ACTIVE:
                          rules:
                            - if: stop > 0
                              then: IDLE -> ctrl_state
                  - name: pulse
                    variable: pulse_state
                    initial: LOW
                    states:
                      - LOW:
                          rules:
                            - if: ctrl_state > 0
                              then:
                                - HIGH -> pulse_state
                                - led * 0 + 1 -> led
                              else:
                                - led * 0 + 0 -> led
                      - HIGH:
                          rules:
                            - if: ctrl_state == 0
                              then:
                                - LOW -> pulse_state
                                - led * 0 + 0 -> led
                              else:
                                - led * 0 + 1 -> led
                """,
            )

            system = NncSystem.from_yaml(str(system_file))
            assert system.step({"start": 0.0, "stop": 0.0}) == {"led": 0.0}
            assert system.step({"start": 1.0, "stop": 0.0}) == {"led": 0.0}
            assert system.step({"start": 0.0, "stop": 0.0}) == {"led": 1.0}
            assert system.step({"start": 0.0, "stop": 1.0}) == {"led": 1.0}
            assert system.step({"start": 0.0, "stop": 0.0}) == {"led": 0.0}
            assert system.constants["ctrl__ACTIVE"].value == 1.0
            assert system.constants["pulse__HIGH"].value == 1.0

    def test_fsm_state_constants_are_referenceable_with_dotted_sugar(self):
        with TempDirContext() as tmp_dir:
            system_file = Path(tmp_dir) / "fsm_state_sugar.yaml"
            write_text(
                system_file,
                """
                cells:
                  - id: 1
                    contents:
                      - ctrl_state = 0
                      - monitor_state = 0
                      - start = 0
                      - out = 0
                    input: [start]
                    output: [out]
                fsm:
                  - name: ctrl
                    variable: ctrl_state
                    initial: IDLE
                    states:
                      - IDLE:
                          rules:
                            - if: start > 0
                              then: RUN -> ctrl_state
                      - RUN:
                          rules: []
                  - name: monitor
                    variable: monitor_state
                    initial: WAIT
                    states:
                      - WAIT:
                          rules:
                            - if: ctrl_state == ctrl.IDLE
                              then: 1 -> out
                              else: 0 -> out
                """,
            )

            system = NncSystem.from_yaml(str(system_file))

            assert system.constants["ctrl__IDLE"].value == 0.0
            assert system.constants["ctrl__RUN"].value == 1.0
            assert system.step({"start": 0.0}) == {"out": 1.0}
