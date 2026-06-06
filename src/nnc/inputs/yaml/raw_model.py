"""Internal raw YAML document model for TENNCell loading."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .locations import YamlLocationIndex


@dataclass(slots=True)
class RawYamlDocument:
    """YAML-shaped TENNCell document before resolution.

    The raw document mirrors the source file closely and keeps the loader
    phase separate from the resolved :class:`~nnc.model.system.NncSystem`.
    """

    source_path: Path
    data: dict[str, Any]
    locations: YamlLocationIndex
    module: dict[str, Any] | None
    constants: dict[str, Any] | None
    cells: list[dict[str, Any]]
    imports: list[dict[str, Any]]
    aliases: dict[str, Any] | None
    rules: list[Any]
    fsm: list[dict[str, Any]] | None
    verilog: dict[str, Any] | None

    @classmethod
    def from_data(
        cls,
        source_path: Path,
        data: dict[str, Any],
        locations: YamlLocationIndex | None = None,
    ) -> "RawYamlDocument":
        """Construct a raw TENNCell document from parsed YAML data."""
        return cls(
            source_path=source_path,
            data=data,
            locations=locations or YamlLocationIndex(source_path, {}),
            module=data.get("module"),
            constants=data.get("constants"),
            cells=data.get("cells", []),
            imports=data.get("imports", []),
            aliases=data.get("aliases"),
            rules=data.get("rules", []),
            fsm=data.get("fsm"),
            verilog=data.get("verilog"),
        )
