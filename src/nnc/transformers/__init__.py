"""TENNCell Transformers package for converting AST to various output formats."""

from importlib import import_module

__all__ = [
    "BaseTransformer",
    "PythonTransformer",
    "VerilogTransformer",
    "WebotsTransformer",
]


def __getattr__(name: str):
    if name == "BaseTransformer":
        return import_module(".base_transformer", __name__).BaseTransformer
    if name == "PythonTransformer":
        return import_module(".python_transformer", __name__).PythonTransformer
    if name == "VerilogTransformer":
        return import_module(".verilog_transformer", __name__).VerilogTransformer
    if name == "WebotsTransformer":
        return import_module(".webots_transformer", __name__).WebotsTransformer
    raise AttributeError(name)
