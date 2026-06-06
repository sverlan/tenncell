"""Per-run state for Python TENNCell emission."""

from dataclasses import dataclass, field
from pathlib import Path

from ...model.system import NncSystem


@dataclass
class PythonEmissionContext:
    """Hold the mutable state needed while emitting one Python system."""

    system: NncSystem
    variable_declarations: set[str] = field(default_factory=set)
    composed_mode: bool = False
    class_names: dict[Path, str] = field(default_factory=dict)
    emitted_modules: set[Path] = field(default_factory=set)
