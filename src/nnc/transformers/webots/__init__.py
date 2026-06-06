"""Webots backend helpers for TENNCell transformers."""

from importlib import import_module

__all__ = [
    "WebotsBindingConfig",
    "WebotsConfig",
    "WebotsEmissionContext",
    "parse_webots_section",
]


def __getattr__(name: str):
    if name in {"WebotsBindingConfig", "WebotsConfig"}:
        return getattr(import_module(".webots_config", __name__), name)
    if name == "WebotsEmissionContext":
        return import_module(".emission_context", __name__).WebotsEmissionContext
    if name == "parse_webots_section":
        return import_module(
            ".webots_yaml_section_parser", __name__
        ).parse_webots_section
    raise AttributeError(name)
