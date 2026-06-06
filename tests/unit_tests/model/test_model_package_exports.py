"""Tests for public model package exports."""

from nnc.inputs.yaml.module_config import ImportConfig, ModuleConfig
from nnc.model import (
    Cell,
    NncSystem,
    ImportConfig as ExportedImportConfig,
    ModuleConfig as ExportedModuleConfig,
    ResolvedReference,
    Rule,
)
from nnc.model.cell import Cell as CellClass
from nnc.model.rule import Rule as RuleClass
from nnc.model.system import NncSystem as NncSystemClass
from nnc.model.system import ResolvedReference as ResolvedReferenceClass


def test_public_model_exports():
    """Public names documented for nnc.model should be importable."""
    assert Cell is CellClass
    assert Rule is RuleClass
    assert NncSystem is NncSystemClass
    assert ResolvedReference is ResolvedReferenceClass
    assert ExportedImportConfig is ImportConfig
    assert ExportedModuleConfig is ModuleConfig
