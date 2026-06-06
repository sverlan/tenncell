"""Per-run state for TENNCell Webots controller emission."""

from dataclasses import dataclass

from ...model.system import NncSystem
from .webots_config import WebotsConfig


@dataclass
class WebotsEmissionContext:
    """Hold the mutable state needed while emitting one Webots controller."""

    system: NncSystem
    config: WebotsConfig
