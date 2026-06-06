"""Executable checks for documented public API imports."""

from __future__ import annotations

import importlib
import re
from pathlib import Path


def _documented_public_names() -> list[str]:
    contract_path = (
        Path(__file__).resolve().parents[1] / "contracts" / "public_contracts.md"
    )
    names: list[str] = []
    pattern = re.compile(r"^- `([^`]+)`")
    for line in contract_path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            names.append(match.group(1))
    return names


def test_public_contract_imports_are_available():
    """Every dotted public name in the contract must be importable."""
    for dotted_name in _documented_public_names():
        module_name, _, attribute_name = dotted_name.rpartition(".")
        assert module_name, f"Public name must be dotted: {dotted_name}"
        module = importlib.import_module(module_name)
        assert hasattr(module, attribute_name), dotted_name
