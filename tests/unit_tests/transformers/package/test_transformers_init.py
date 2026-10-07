"""Tests for transformers __init__ module."""

import pytest
from nnc.transformers import (
    BaseTransformer,
    Mc2Transformer,
    PythonTransformer,
    VerilogTransformer,
    WebotsTransformer,
)
from nnc.transformers.base_transformer import BaseTransformer as BaseTransformerClass
from nnc.transformers.mc2_transformer import Mc2Transformer as Mc2TransformerClass
from nnc.transformers.python_transformer import (
    PythonTransformer as PythonTransformerClass,
)
from nnc.transformers.verilog_transformer import (
    VerilogTransformer as VerilogTransformerClass,
)
from nnc.transformers.webots_transformer import (
    WebotsTransformer as WebotsTransformerClass,
)
from nnc.transformers.verilog.hardware_config import (
    ClockConfig,
    ExternalInstance,
    ExternalModuleSchema,
    VerilogEncoding,
    VerilogFixedPointEncoding,
    VerilogLogicEncoding,
    PortConfig,
    RealEncoding,
    ResetConfig,
    VerilogHardwareConfig,
)
from nnc.transformers.webots.webots_config import (
    WebotsBindingConfig,
    WebotsConfig,
    WebotsCsvConfig,
)


class TestTransformersInit:
    """Test the transformers __init__ module imports."""

    def test_base_transformer_import(self):
        """Test that BaseTransformer is imported correctly."""
        assert BaseTransformer is BaseTransformerClass

    def test_mc2_transformer_import(self):
        """Test that Mc2Transformer is imported correctly."""
        assert Mc2Transformer is Mc2TransformerClass

    def test_python_transformer_import(self):
        """Test that PythonTransformer is imported correctly."""
        assert PythonTransformer is PythonTransformerClass

    def test_verilog_transformer_import(self):
        """Test that VerilogTransformer is imported correctly."""
        assert VerilogTransformer is VerilogTransformerClass

    def test_webots_transformer_import(self):
        """Test that WebotsTransformer is imported correctly."""
        assert WebotsTransformer is WebotsTransformerClass

    def test_all_exports(self):
        """Test that __all__ exports are correct."""
        from nnc.transformers import __all__

        assert "BaseTransformer" in __all__
        assert "Mc2Transformer" in __all__
        assert "PythonTransformer" in __all__
        assert "VerilogTransformer" in __all__
        assert "WebotsTransformer" in __all__
        assert len(__all__) == 5

    def test_missing_export_raises_attribute_error(self):
        """Test that unknown names are rejected by the lazy loader."""
        with pytest.raises(AttributeError, match="MissingTransformer"):
            getattr(
                __import__("nnc.transformers", fromlist=["*"]), "MissingTransformer"
            )


class TestVerilogInit:
    """Test the verilog backend __init__ module imports."""

    def test_config_exports(self):
        """Test that public Verilog config classes are package-exported."""
        from nnc.transformers.verilog import (
            ClockConfig as ExportedClockConfig,
            ExternalInstance as ExportedExternalInstance,
            ExternalModuleSchema as ExportedExternalModuleSchema,
            VerilogEncoding as ExportedVerilogEncoding,
            VerilogFixedPointEncoding as ExportedVerilogFixedPointEncoding,
            VerilogLogicEncoding as ExportedVerilogLogicEncoding,
            PortConfig as ExportedPortConfig,
            RealEncoding as ExportedRealEncoding,
            ResetConfig as ExportedResetConfig,
            VerilogHardwareConfig as ExportedVerilogHardwareConfig,
        )

        assert ExportedClockConfig is ClockConfig
        assert ExportedExternalInstance is ExternalInstance
        assert ExportedExternalModuleSchema is ExternalModuleSchema
        assert ExportedVerilogEncoding is VerilogEncoding
        assert ExportedVerilogFixedPointEncoding is VerilogFixedPointEncoding
        assert ExportedVerilogLogicEncoding is VerilogLogicEncoding
        assert ExportedPortConfig is PortConfig
        assert ExportedRealEncoding is RealEncoding
        assert ExportedResetConfig is ResetConfig
        assert ExportedVerilogHardwareConfig is VerilogHardwareConfig

    def test_missing_export_raises_attribute_error(self):
        """Test that unknown names are rejected by the lazy loader."""
        with pytest.raises(AttributeError, match="MissingEmitter"):
            getattr(
                __import__("nnc.transformers.verilog", fromlist=["*"]),
                "MissingEmitter",
            )


class TestWebotsInit:
    """Test the webots backend __init__ module imports."""

    def test_config_exports(self):
        """Test that public Webots config classes are package-exported."""
        from nnc.transformers.webots import (
            WebotsBindingConfig as ExportedWebotsBindingConfig,
            WebotsConfig as ExportedWebotsConfig,
            WebotsCsvConfig as ExportedWebotsCsvConfig,
        )

        assert ExportedWebotsBindingConfig is WebotsBindingConfig
        assert ExportedWebotsConfig is WebotsConfig
        assert ExportedWebotsCsvConfig is WebotsCsvConfig

    def test_missing_export_raises_attribute_error(self):
        """Test that unknown names are rejected by the lazy loader."""
        with pytest.raises(AttributeError, match="MissingController"):
            getattr(
                __import__("nnc.transformers.webots", fromlist=["*"]),
                "MissingController",
            )
