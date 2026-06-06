"""Per-run state for Verilog TENNCell generation."""

from dataclasses import dataclass, field

from ....model.system import NncSystem
from ..hardware_config import PortConfig, VerilogHardwareConfig, VerilogTypeInfo


@dataclass
class VerilogEmissionContext:
    """Hold the mutable state needed while emitting one Verilog system."""

    system: NncSystem
    config: VerilogHardwareConfig
    local_variables: list[str] = field(default_factory=list)
    top_ports: dict[str, PortConfig] = field(default_factory=dict)
    external_input_bindings: dict[str, tuple[str, PortConfig]] = field(
        default_factory=dict
    )
    external_output_bindings: dict[str, tuple[str, PortConfig]] = field(
        default_factory=dict
    )
    import_output_bindings: dict[str, tuple[str, PortConfig]] = field(
        default_factory=dict
    )
    resolved_var_types: dict[str, VerilogTypeInfo] = field(default_factory=dict)
    reference_inputs: dict[str, str] = field(default_factory=dict)
    conversion_helpers: dict[tuple[str, int, bool, int, str, int, bool, int], str] = (
        field(default_factory=dict)
    )
    literal_params: dict[tuple[float, int, int, bool], str] = field(
        default_factory=dict
    )
