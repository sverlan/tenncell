"""nnc-gen reports YAML origins and context for unsupported RTL rule expressions."""

from pathlib import Path
from unittest.mock import patch

import pytest

from nnc.cli_transform import main


FIXTURES = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "transformers"
    / "verilog"
    / "input"
    / "diagnostics"
)


@pytest.mark.parametrize("target", ["verilog", "sva"])
@pytest.mark.parametrize(
    "model, origin, line, role",
    [
        ("producer", "producer", 4, "producer"),
        ("guard", "guard", 4, "guard"),
        ("structured", "structured", 6, "producer"),
        ("repeat", "repeat", 13, "producer"),
        ("fsm", "fsm", 11, "producer"),
        ("included", "fragment", 2, "producer"),
        ("imported", "producer", 4, "producer"),
        ("transition_string", "transition_string", 12, "guard"),
        ("transition_structured", "transition_structured", 14, "guard"),
        ("else", "else", 8, "producer"),
        ("fsm_else", "fsm_else", 14, "producer"),
        ("fsm_scalar", "fsm_scalar", 10, "producer"),
        ("inherited_guard", "inherited_guard", 6, "guard"),
    ],
)
def test_unsupported_multiplication_reports_origin_and_rule(
    target, model, origin, line, role, tmp_path, capsys
):
    options = ["--sva-steps", "1"] if target == "sva" else []
    with patch(
        "sys.argv",
        [
            "nnc-gen",
            str(FIXTURES / f"{model}.yaml"),
            "-t",
            target,
            "-o",
            str(tmp_path),
            *options,
        ],
    ):
        code = main()

    error = capsys.readouterr().err
    assert code == 1
    assert f"{FIXTURES / f'{origin}.yaml'}:{line}: " in error
    assert (
        "Verilog export does not support variable-by-variable multiplication" in error
    )
    assert f"in {role} of rule:" in error
    assert "x * y" in error
    consumer = "state" if model.startswith("transition_") else "z"
    assert f"-> {consumer}" in error


@pytest.mark.parametrize("target", ["verilog", "sva"])
@pytest.mark.parametrize(
    "model, diagnostic, expression",
    [
        ("division", "general division", "x / y"),
        ("function", "function calls", "sin(x)"),
    ],
)
def test_other_pre_emission_errors_have_rule_context(
    target, model, diagnostic, expression, tmp_path, capsys
):
    options = ["--sva-steps", "1"] if target == "sva" else []
    with patch(
        "sys.argv",
        [
            "nnc-gen",
            str(FIXTURES / f"{model}.yaml"),
            "-t",
            target,
            "-o",
            str(tmp_path),
            *options,
        ],
    ):
        code = main()

    error = capsys.readouterr().err
    assert code == 1
    assert f"{FIXTURES / f'{model}.yaml'}:5:" in error
    assert diagnostic in error
    assert "in producer of rule:" in error
    assert expression in error


@pytest.mark.parametrize("target", ["verilog", "sva"])
def test_empty_branches_do_not_require_rtl_support_for_unused_condition(
    target, tmp_path, capsys
):
    options = ["--sva-steps", "1"] if target == "sva" else []
    with patch(
        "sys.argv",
        [
            "nnc-gen",
            str(FIXTURES / "empty_branch.yaml"),
            "-t",
            target,
            "-o",
            str(tmp_path),
            *options,
        ],
    ):
        code = main()

    assert code == 0, capsys.readouterr().err
