"""MC2 query-file transformer for TENNCell verification raw entries."""

from __future__ import annotations

from pathlib import Path

from ..inputs.yaml.locations import YamlLocationIndex
from ..model.system import NncSystem
from ..verification.binding import BoundVerification
from ..verification.mc2 import QUERIES_SUFFIX, render_mc2
from .base_transformer import BaseTransformer


class Mc2Transformer(BaseTransformer):
    """Emit MC2 query, ID, and trace-column files from ``mc2`` raw entries."""

    def __init__(
        self, verification_configs: dict[Path, BoundVerification | None] | None = None
    ) -> None:
        """Create an MC2 transformer.

        Args:
            verification_configs: Optional mapping from loaded YAML source paths
                to bound verification configs (``None`` when the section is absent).
        """
        super().__init__()
        self.verification_configs = verification_configs or {}

    def set_verification_configs(
        self, configs: dict[Path, BoundVerification | None]
    ) -> None:
        """Replace the bound verification configs used during emission.

        Args:
            configs: Mapping from TENNCell source paths to bound verification
                configs.
        """
        self.verification_configs = configs

    def get_file_extension(self) -> str:
        """Return the suffix of the MC2 query file."""
        return QUERIES_SUFFIX

    def transform(self, system: NncSystem) -> str:
        """Return the MC2 query file for a TENNCell system.

        Args:
            system: Root TENNCell system loaded from YAML.

        Returns:
            MC2 query file content, one query per line.
        """
        return self.transform_files(system)[QUERIES_SUFFIX]

    def transform_files(self, system: NncSystem) -> dict[str, str]:
        """Return the MC2 query, ID, and trace-column files for a system.

        Args:
            system: Root TENNCell system loaded from YAML.

        Returns:
            File contents keyed by ``.mc2.pltl``, ``.mc2.ids``, and
            ``.mc2.columns``.

        Raises:
            ValueError: If the system has no ``verification.backends.mc2.raw``
                entries.
            YamlLocatedError: If a raw entry is not a single MC2 query.
        """
        self.warnings = []
        bound = self._config_for(system)
        if bound is None or not bound.raw.get("mc2"):
            raise ValueError(
                "No MC2 raw verification entries found "
                "(verification.backends.mc2.raw)"
            )
        locations = system.source_locations or YamlLocationIndex(
            _source_path(system), {}
        )
        artifacts = render_mc2(bound, locations)
        skipped = [
            stub.id
            for stub in bound.config.properties
            if stub.targets is None or "mc2" in stub.targets
        ]
        if skipped:
            self.warnings.append(
                "generic verification properties are not emitted by the MC2 raw "
                f"backend yet: {', '.join(skipped)}"
            )
        untraced = [
            column
            for column in artifacts.columns
            if column not in system.output_variables
        ]
        if untraced:
            self.warnings.append(
                "MC2 trace columns are not root outputs, so nnc-sim traces will "
                f"not contain them: {', '.join(untraced)}"
            )
        return artifacts.files()

    def _config_for(self, system: NncSystem) -> BoundVerification | None:
        """Return the bound verification config of a loaded system."""
        source_path = _source_path(system)
        if source_path not in self.verification_configs:
            raise ValueError(f"Missing verification configuration for '{source_path}'")
        return self.verification_configs[source_path]


def _source_path(system: NncSystem) -> Path:
    """Return the YAML source path of a system, requiring one."""
    if system.source_path is None:
        raise ValueError("MC2 export requires systems loaded from YAML files")
    return system.source_path
