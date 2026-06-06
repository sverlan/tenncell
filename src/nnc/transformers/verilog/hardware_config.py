"""Verilog hardware configuration dataclasses."""

from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias

from .generation.encodings import (
    VerilogEncoding as _VerilogEncoding,
    VerilogFixedPointEncoding as _VerilogFixedPointEncoding,
    VerilogLogicEncoding as _VerilogLogicEncoding,
)

VerilogEncoding = _VerilogEncoding
VerilogFixedPointEncoding = _VerilogFixedPointEncoding
VerilogLogicEncoding = _VerilogLogicEncoding


@dataclass(slots=True)
class VerilogLogicTypeInfo:
    """Verilog type hint for a logic or packed-vector signal."""

    kind: Literal["logic"]
    width: int
    signed: bool = False


@dataclass(slots=True)
class VerilogFixedPointTypeInfo:
    """Verilog type hint for a fixed-point encoded internal variable."""

    kind: Literal["fixed_point"]
    width: int
    frac_bits: int
    signed: bool = False


VerilogTypeInfo: TypeAlias = VerilogLogicTypeInfo | VerilogFixedPointTypeInfo


@dataclass(slots=True)
class RealEncoding:
    """Fixed-point encoding for one generated Verilog module.

    Args:
        kind: Encoding family, currently ``fixed_point`` in the public YAML
            contract.
        signed: Whether the generated storage uses signed arithmetic.
        width: Total bit width of the encoded value.
        frac_bits: Number of fractional bits in the fixed-point encoding.

    Validation assumptions:
        The Verilog YAML parser requires all four fields when a ``real_encoding``
        block is present. Generated RTL assumes the values are integers and that
        ``width`` and ``frac_bits`` are compatible.
    """

    kind: str
    signed: bool
    width: int
    frac_bits: int

    def to_verilog_encoding(self) -> VerilogFixedPointEncoding:
        """Return the backend encoding object used by Verilog emitters."""
        return VerilogFixedPointEncoding(
            kind="fixed",
            width=self.width,
            signed=self.signed,
            frac_bits=self.frac_bits,
        )


@dataclass(slots=True)
class ClockConfig:
    """Clock configuration for generated hardware modules.

    Args:
        name: Top-level clock signal name. Defaults to ``clk`` when omitted.
    """

    name: str = "clk"


@dataclass(slots=True)
class ResetConfig:
    """Reset configuration for generated hardware modules.

    Args:
        name: Top-level reset signal name. Defaults to ``rst`` when omitted.
        active_high: ``True`` for active-high reset, ``False`` for active-low.
    """

    name: str = "rst"
    active_high: bool = True


@dataclass(slots=True)
class PortConfig:
    """Top-level or external module port description.

    Args:
        name: Port name in the generated RTL or external header.
        direction: Port direction from the parsed YAML, typically ``input`` or
            ``output``.
        kind: Port kind. The public contract defaults this to ``logic``.
        width: Port width in bits. The current contract defaults this to ``1``.
        signed: Whether the generated signal is signed. Defaults to ``False``.
        rename: Optional Verilog name to emit for the port.

    Validation assumptions:
        The Verilog parser accepts ``kind`` as an optional public field and
        defaults to ``logic`` when omitted.
    """

    name: str
    dir: str
    kind: str = "logic"
    width: int = 1
    signed: bool = False
    rename: str | None = None

    @property
    def verilog_name(self) -> str:
        """Return the emitted Verilog name for the port."""
        return self.rename or self.name


@dataclass(slots=True)
class ExternalModuleSchema:
    """Reusable declaration for an external RTL module.

    Args:
        module: External module name from the schema or header file.
        parameters: Parameter defaults declared by the header.
        ports: Port declarations that define the external module interface.
        source_path: Absolute path to the parsed header file.

    Validation assumptions:
        The parser populates ``source_path`` when the header is loaded from disk.
        ``ports`` are expected to be compatible with the external instance wiring.
    """

    module: str
    parameters: dict[str, int | float | str] = field(default_factory=dict)
    ports: list[PortConfig] = field(default_factory=list)
    source_path: str | None = None

    @property
    def name(self) -> str:
        """Return the external module name for compatibility."""
        return self.module


@dataclass(slots=True)
class ExternalInstance:
    """Concrete instance of an external RTL module.

    Args:
        header: Absolute path to the header file or resolved header key.
        schema: Inline schema description for the reusable module definition.
        alias: Instance alias used in the generated RTL and connections.
        parameters: Instance parameter overrides.
        connections: Mapping of external port names to TENNCell reference strings or
            literal values.
        definition: Parsed external schema definition, or ``None`` before the
            header has been resolved.

    Validation assumptions:
        The Verilog loader resolves ``header`` or ``schema`` to a parsed
        :class:`ExternalModuleSchema` before generation.
        ``connections`` should target names declared by the header.
    """

    alias: str
    header: str | None = None
    schema: dict[str, Any] | None = None
    parameters: dict[str, int | float | str] = field(default_factory=dict)
    connections: dict[str, str] = field(default_factory=dict)
    definition: ExternalModuleSchema | None = None


@dataclass(slots=True)
class VerilogHardwareConfig:
    """Verilog-specific configuration parsed from the YAML ``verilog`` section.

    Args:
        real_encoding: Fixed-point encoding used for generated module state.
        clock: Clock description for the generated module.
        reset: Reset description for the generated module.
        ports: Top-level ports exposed by the generated module.
        types: Optional Verilog-only hints for non-interface internal variables.
        externals: External RTL modules declared in the Verilog configuration.

    Validation assumptions:
        The Verilog backend expects ``real_encoding`` to be present for actual
        code generation. The parser may still build a partial object when a file
        only provides legacy or incomplete metadata.
    """

    real_encoding: RealEncoding | None = None
    clock: ClockConfig = field(default_factory=ClockConfig)
    reset: ResetConfig = field(default_factory=ResetConfig)
    ports: list[PortConfig] = field(default_factory=list)
    types: dict[str, VerilogTypeInfo] = field(default_factory=dict)
    type_lines: dict[str, int | None] = field(default_factory=dict)
    externals: list[ExternalInstance] = field(default_factory=list)

    @property
    def top_ports(self) -> list[PortConfig]:
        """Return top-level ports for compatibility with the old contract."""
        return self.ports
