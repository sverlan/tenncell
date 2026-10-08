"""CLI contract tests for `nnc-gen`."""

from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import shutil

import pytest

from nnc.cli_transform import _collect_import_closure, _parse_verilog_configs
from nnc.inputs.yaml.module_config import ImportConfig
from nnc.model.system import NncSystem
from nnc._version import __version__
from nnc.cli_transform import TRANSFORMERS, get_transformer, main
from nnc.transformers import (
    Mc2Transformer,
    PythonTransformer,
    VerilogTransformer,
    WebotsTransformer,
)


def _fixture_path(name: str) -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures" / "functional" / name


def _verilog_fixture_path(*parts: str) -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "transformers"
        / "verilog"
        / "input"
        / Path(*parts)
    )


def _webots_fixture_path(*parts: str) -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "transformers"
        / "webots"
        / Path(*parts)
    )


class TestGetTransformer:
    def test_get_transformer_python(self):
        transformer = get_transformer("python")
        assert isinstance(transformer, PythonTransformer)

    def test_get_transformer_verilog(self):
        transformer = get_transformer("verilog")
        assert isinstance(transformer, VerilogTransformer)

    def test_get_transformer_webots(self):
        transformer = get_transformer("webots")
        assert isinstance(transformer, WebotsTransformer)

    def test_get_transformer_mc2(self):
        transformer = get_transformer("mc2")
        assert isinstance(transformer, Mc2Transformer)

    def test_get_transformer_invalid_type(self):
        with pytest.raises(ValueError) as excinfo:
            get_transformer("invalid")
        assert "Unsupported transformation type 'invalid'" in str(excinfo.value)
        assert "Available types: python" in str(excinfo.value)


class TestMain:
    def test_main_help(self):
        with patch("sys.argv", ["nnc-gen", "--help"]):
            with pytest.raises(SystemExit) as excinfo:
                main()
            assert excinfo.value.code == 0

    def test_main_version(self):
        with patch("sys.argv", ["nnc-gen", "--version"]):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                with pytest.raises(SystemExit) as excinfo:
                    main()

        assert excinfo.value.code == 0
        assert mock_stdout.getvalue() == f"nnc-gen {__version__}\n"

    def test_main_no_args(self):
        with patch("sys.argv", ["nnc-gen"]):
            with pytest.raises(SystemExit) as excinfo:
                main()
            assert excinfo.value.code != 0

    def test_main_missing_type(self):
        with patch("sys.argv", ["nnc-gen", "test.yaml"]):
            with pytest.raises(SystemExit) as excinfo:
                main()
            assert excinfo.value.code != 0

    def test_main_invalid_type(self):
        with patch("sys.argv", ["nnc-gen", "test.yaml", "-t", "invalid"]):
            with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                with pytest.raises(SystemExit) as excinfo:
                    main()
                assert excinfo.value.code == 2
                assert (
                    "Error: Unsupported transformation type 'invalid'"
                    not in mock_stderr.getvalue()
                )

    def test_main_file_not_found(self):
        with patch("sys.argv", ["nnc-gen", "nonexistent.yaml", "-t", "python"]):
            with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                main()
                assert (
                    "Error: File 'nonexistent.yaml' not found" in mock_stderr.getvalue()
                )

    def test_main_successful_transformation(self):
        with TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir) / "generated" / "python"
            input_file = _fixture_path("example1.yaml")

            with patch(
                "sys.argv",
                [
                    "nnc-gen",
                    str(input_file),
                    "-t",
                    "python",
                    "-o",
                    str(out_dir),
                    "--verbose",
                ],
            ):
                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                    main()

            assert (out_dir / "example1.py").exists()
            assert out_dir.exists()
            output = mock_stdout.getvalue()
            assert "Processing:" in output
            assert "Transformation complete." in output

    def test_main_with_output_suffix(self):
        with TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir)
            input_file = _fixture_path("example1.yaml")

            with patch(
                "sys.argv",
                [
                    "nnc-gen",
                    str(input_file),
                    "-t",
                    "python",
                    "-o",
                    str(out_dir),
                    "--output-suffix",
                    "_generated",
                ],
            ):
                main()

            assert (out_dir / "example1_generated.py").exists()

    @pytest.mark.parametrize(
        ("transform_type", "input_file", "extra_args", "expected_files"),
        [
            (
                "python",
                _fixture_path("example1.yaml"),
                [],
                ("example1_generated.py",),
            ),
            (
                "verilog",
                _verilog_fixture_path("imports_externals", "controller.yaml"),
                [
                    "--import-paths",
                    str(_verilog_fixture_path("imports_externals")),
                ],
                ("controller_generated.sv", "sensor_generated.sv"),
            ),
            (
                "webots",
                _webots_fixture_path("input", "sensor_led.yaml"),
                [],
                ("sensor_led_generated.py",),
            ),
        ],
    )
    def test_main_standard_options_smoke(
        self, transform_type, input_file, extra_args, expected_files
    ):
        with TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir) / "generated"
            with patch(
                "sys.argv",
                [
                    "nnc-gen",
                    str(input_file),
                    "-t",
                    transform_type,
                    "-o",
                    str(out_dir),
                    "--output-suffix",
                    "_generated",
                    "--verbose",
                    *extra_args,
                ],
            ):
                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                    main()

            assert out_dir.exists()
            for expected_file in expected_files:
                assert (out_dir / expected_file).exists()

            output = mock_stdout.getvalue()
            assert "Processing:" in output
            assert "Transformation complete." in output

    def test_main_transformation_error(self):
        with TemporaryDirectory() as tmp_dir:
            tmp_dir = Path(tmp_dir)
            bad_file = tmp_dir / "bad.yaml"
            bad_file.write_text("module:\n  name: bad\nverilog: [\n", encoding="utf-8")

            with patch(
                "sys.argv",
                ["nnc-gen", str(bad_file), "-t", "python", "--verbose"],
            ):
                with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                    main()
                    error_output = mock_stderr.getvalue()
                    assert f"Error processing '{bad_file}'" in error_output

    def test_main_multiple_files(self):
        with TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir)
            input_files = [
                _fixture_path("example1.yaml"),
                _fixture_path("example2.yaml"),
            ]

            with patch(
                "sys.argv",
                [
                    "nnc-gen",
                    *(str(path) for path in input_files),
                    "-t",
                    "python",
                    "-o",
                    str(out_dir),
                ],
            ):
                main()

            assert (out_dir / "example1.py").exists()
            assert (out_dir / "example2.py").exists()

    def test_transformers_registry(self):
        assert "python" in TRANSFORMERS
        assert "verilog" in TRANSFORMERS
        assert "webots" in TRANSFORMERS
        assert TRANSFORMERS["python"] == PythonTransformer
        assert TRANSFORMERS["verilog"] == VerilogTransformer
        assert TRANSFORMERS["webots"] == WebotsTransformer

    def test_main_python_imports_emit_single_file(self):
        with TemporaryDirectory() as tmp_dir:
            tmp_dir = Path(tmp_dir)
            lib_dir = tmp_dir / "lib"
            out_dir = tmp_dir / "out"
            lib_dir.mkdir(parents=True, exist_ok=True)
            out_dir.mkdir(parents=True, exist_ok=True)

            fixture_root = (
                Path(__file__).resolve().parents[1]
                / "fixtures"
                / "transformers"
                / "python"
                / "input"
            )
            shutil.copyfile(
                fixture_root / "composed_child.yaml", lib_dir / "composed_child.yaml"
            )
            shutil.copyfile(
                fixture_root / "composed_root.yaml", tmp_dir / "controller.yaml"
            )

            with patch(
                "sys.argv",
                [
                    "nnc-gen",
                    str(tmp_dir / "controller.yaml"),
                    "-t",
                    "python",
                    "-o",
                    str(out_dir),
                    "--import-path",
                    str(lib_dir),
                ],
            ):
                main()

            assert (out_dir / "controller.py").exists()
            assert not (out_dir / "sensor.py").exists()

    def test_main_verilog_import_paths_string_uses_search_paths(self):
        with TemporaryDirectory() as tmp_dir:
            tmp_dir = Path(tmp_dir)
            fixture_root = (
                Path(__file__).resolve().parents[1]
                / "fixtures"
                / "transformers"
                / "verilog"
                / "input"
                / "imports_externals"
            )
            out_dir = tmp_dir / "out"
            out_dir.mkdir(parents=True, exist_ok=True)

            with patch(
                "sys.argv",
                [
                    "nnc-gen",
                    str(fixture_root / "controller.yaml"),
                    "-t",
                    "verilog",
                    "-o",
                    str(out_dir),
                    "--import-paths",
                    str(fixture_root),
                ],
            ):
                main()

            assert (out_dir / "controller.sv").exists()
            assert (out_dir / "sensor.sv").exists()

    def test_collect_import_closure_skips_duplicates_and_missing_systems(self):
        root = NncSystem()
        root.source_path = Path("root.yaml")
        child = NncSystem()
        child.source_path = Path("child.yaml")
        root.imports = [
            ImportConfig(module="child.yaml", alias="first", system=child),
            ImportConfig(module="child.yaml", alias="second", system=child),
            ImportConfig(module="missing.yaml", alias="missing", system=None),
        ]

        ordered = _collect_import_closure(root)
        assert [system.source_path for system in ordered] == [
            child.source_path,
            root.source_path,
        ]

    def test_parse_verilog_configs_requires_loaded_sources(self):
        system = NncSystem()
        with pytest.raises(
            ValueError, match="Verilog export requires systems loaded from YAML files"
        ):
            _parse_verilog_configs([system], {}, [])


class TestWebotsMainContract:
    def test_main_webots_success_path(self):
        with TemporaryDirectory() as tmp_dir:
            tmp_dir = Path(tmp_dir)
            input_file = _webots_fixture_path("input", "sensor_led.yaml")
            out_dir = tmp_dir / "generated"

            with patch(
                "sys.argv",
                [
                    "nnc-gen",
                    str(input_file),
                    "-t",
                    "webots",
                    "-o",
                    str(out_dir),
                    "--output-suffix",
                    "_generated",
                ],
            ):
                main()

            assert (out_dir / "sensor_led_generated.py").exists()

    def test_main_webots_missing_section(self):
        input_file = _webots_fixture_path("input", "missing_webots.yaml")
        with patch(
            "sys.argv",
            ["nnc-gen", str(input_file), "-t", "webots"],
        ):
            with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                main()
                error_output = mock_stderr.getvalue()
                assert f"Error processing '{input_file}'" in error_output
                assert "Missing required Webots section 'webots'" in error_output

    def test_main_webots_missing_input_binding(self):
        input_file = _webots_fixture_path("input", "missing_input_binding.yaml")
        with patch(
            "sys.argv",
            ["nnc-gen", str(input_file), "-t", "webots"],
        ):
            with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                main()
                error_output = mock_stderr.getvalue()
                assert f"Error processing '{input_file}'" in error_output
                assert "missing an input binding for 'input_x'" in error_output

    def test_main_webots_missing_output_binding(self):
        input_file = _webots_fixture_path("input", "missing_output_binding.yaml")
        with patch(
            "sys.argv",
            ["nnc-gen", str(input_file), "-t", "webots"],
        ):
            with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                main()
                error_output = mock_stderr.getvalue()
                assert f"Error processing '{input_file}'" in error_output
                assert "missing an output binding for 'out'" in error_output

    def test_main_webots_invalid_binding_method_types(self):
        input_file = _webots_fixture_path("input", "invalid_binding_method.yaml")
        with patch(
            "sys.argv",
            ["nnc-gen", str(input_file), "-t", "webots"],
        ):
            with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                main()
                error_output = mock_stderr.getvalue()
                assert f"Error processing '{input_file}'" in error_output
                assert "read_method must be a string" in error_output


def test_python_generation_rejects_custom_function_and_continues_batch(monkeypatch):
    from nnc.parser.ast.value.math_functions import MathFunctions

    monkeypatch.setitem(MathFunctions._functions, "double_it", lambda value: 2 * value)
    monkeypatch.setitem(MathFunctions._function_arg_counts, "double_it", 1)
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        custom = tmp_path / "custom.yaml"
        custom.write_text(
            "cells:\n  - id: 1\n    contents:\n      - x = 0\n    output: [x]\n"
            "rules:\n  - x * 0 + double_it(0.5) -> x\n",
            encoding="utf-8",
        )
        out_dir = tmp_path / "out"
        with patch(
            "sys.argv",
            [
                "nnc-gen",
                str(custom),
                str(_fixture_path("example1.yaml")),
                "-t",
                "python",
                "-o",
                str(out_dir),
            ],
        ):
            with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                assert main() == 1

        assert "Function 'double_it' is not available in generated Python code" in (
            mock_stderr.getvalue()
        )
        assert not (out_dir / "custom.py").exists()
        assert (out_dir / "example1.py").exists()


def test_python_generation_rejects_non_model_file_and_continues_batch():
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        header = tmp_path / "device.header.yaml"
        header.write_text(
            "schema:\n  name: device\n  ports:\n    - name: ready\n"
            "      direction: output\n      width: 1\n",
            encoding="utf-8",
        )
        out_dir = tmp_path / "out"
        with patch(
            "sys.argv",
            [
                "nnc-gen",
                str(header),
                str(_fixture_path("example1.yaml")),
                "-t",
                "python",
                "-o",
                str(out_dir),
            ],
        ):
            with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                assert main() == 1

        assert "nothing to generate" in mock_stderr.getvalue()
        assert not (out_dir / "device.header.py").exists()
        assert (out_dir / "example1.py").exists()


def _mc2_fixture_path(*parts: str) -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures" / Path(*parts)


class TestMc2MainContract:
    """CLI contract for ``nnc-gen -t mc2``."""

    def test_writes_query_ids_and_columns_files_with_suffix(self):
        input_file = _mc2_fixture_path(
            "transformers", "mc2", "input", "imported_mc2.yaml"
        )
        expected_dir = _mc2_fixture_path("transformers", "mc2", "expected")
        with TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir)
            with patch(
                "sys.argv",
                [
                    "nnc-gen",
                    str(input_file),
                    "-t",
                    "mc2",
                    "-o",
                    str(out_dir),
                    "--output-suffix",
                    "_gen",
                ],
            ):
                assert main() == 0

            for suffix in (".mc2.pltl", ".mc2.ids", ".mc2.columns"):
                generated = (out_dir / f"imported_mc2_gen{suffix}").read_text(
                    encoding="utf-8"
                )
                expected = (expected_dir / f"imported_mc2{suffix}").read_text(
                    encoding="utf-8"
                )
                assert generated == expected

    def test_prints_skipped_property_warning(self):
        input_file = _mc2_fixture_path("verification", "input", "fsm_counter_mc2.yaml")
        with TemporaryDirectory() as tmp_dir:
            with patch(
                "sys.argv", ["nnc-gen", str(input_file), "-t", "mc2", "-o", tmp_dir]
            ):
                with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                    assert main() == 0

        assert (
            "Warning: " in mock_stderr.getvalue()
            and "generic verification properties are not emitted by the MC2 raw "
            "backend yet: bounded"
            in mock_stderr.getvalue()
        )

    def test_invalid_file_fails_but_batch_continues(self):
        good_file = _mc2_fixture_path("verification", "input", "fsm_counter_mc2.yaml")
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            bad_file = tmp_path / "bad.yaml"
            bad_file.write_text(
                "cells:\n  - id: 1\n    contents:\n      - x = 0\n"
                "verification:\n  backends:\n    prism: {}\n",
                encoding="utf-8",
            )
            missing_raw = tmp_path / "no_raw.yaml"
            missing_raw.write_text(
                "cells:\n  - id: 1\n    contents:\n      - x = 0\n",
                encoding="utf-8",
            )
            out_dir = tmp_path / "out"
            with patch(
                "sys.argv",
                [
                    "nnc-gen",
                    str(bad_file),
                    str(missing_raw),
                    str(good_file),
                    "-t",
                    "mc2",
                    "-o",
                    str(out_dir),
                ],
            ):
                with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                    assert main() == 1

            errors = mock_stderr.getvalue()
            assert "bad.yaml:7: Verification backend 'prism' is reserved" in errors
            assert "No MC2 raw verification entries found" in errors
            assert (out_dir / "fsm_counter_mc2.mc2.pltl").exists()
            assert not (out_dir / "bad.mc2.pltl").exists()
