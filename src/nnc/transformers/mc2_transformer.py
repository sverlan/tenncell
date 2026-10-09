"""MC2 query-file transformer for TENNCell verification entries."""

from __future__ import annotations

from pathlib import Path

from ..inputs.yaml.locations import YamlLocationIndex
from ..model.system import NncSystem
from ..verification.binding import BoundVerification
from ..verification.mc2 import QUERIES_SUFFIX, render_mc2
from .base_transformer import BaseTransformer
from .webots.webots_config import WebotsCsvConfig

# Trace separators MC2 v2.0beta2 reads: whitespace by default, ";" with -snoopy.
MC2_TRACE_DELIMITERS = (" ", "\t", ";")

NOTHING_TO_EMIT = (
    "No MC2 verification entries found: add verification.backends.mc2.raw "
    "entries or verification.properties that MC2 can check"
)


class Mc2Transformer(BaseTransformer):
    """Emit MC2 query, ID, and trace-column files from ``mc2`` raw entries and
    generic verification properties."""

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
        self.webots_csv_configs: dict[Path, WebotsCsvConfig | None] = {}

    def set_webots_csv_configs(
        self, configs: dict[Path, WebotsCsvConfig | None]
    ) -> None:
        """Set the Webots CSV log configuration of each system, if any.

        Used only for trace-source warnings: columns listed in
        ``webots.csv.variables`` are recorded by the Webots controller's log.

        Args:
            configs: Mapping from TENNCell source paths to the parsed
                ``webots.csv`` config, or ``None`` when the model has none.
        """
        self.webots_csv_configs = configs

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
            ValueError: If nothing is emitted: no ``verification.backends.mc2.raw``
                entries and no generic property for MC2.
            YamlLocatedError: If a raw entry is not a single MC2 query, or a
                generic property cannot be emitted (see ``render_mc2``).
        """
        self.warnings = []
        bound = self._config_for(system)
        if bound is None:
            raise ValueError(NOTHING_TO_EMIT)
        locations = system.source_locations or YamlLocationIndex(
            _source_path(system), {}
        )
        artifacts = render_mc2(bound, locations)
        self.warnings.extend(artifacts.warnings)
        if not artifacts.queries:
            raise ValueError(NOTHING_TO_EMIT)
        self._warn_about_trace_sources(system, artifacts.columns)
        return artifacts.files()

    def _warn_about_trace_sources(
        self, system: NncSystem, columns: tuple[str, ...]
    ) -> None:
        """Warn when no known trace source records a column MC2 needs.

        Two trace sources are known: ``nnc-sim`` CSV output (root output
        variables only) and, when the model has ``webots.csv``, the Webots
        controller's CSV log (``webots.csv.variables``).
        """
        webots_csv = self.webots_csv_configs.get(_source_path(system))
        outputs = set(system.output_variables)
        if webots_csv is None:
            untraced = [column for column in columns if column not in outputs]
            if untraced:
                self.warnings.append(
                    "MC2 trace columns are not root outputs, so nnc-sim traces will "
                    f"not contain them: {', '.join(untraced)}"
                )
            return

        logged = set(webots_csv.variables)
        untraced = [column for column in columns if column not in outputs | logged]
        if untraced:
            self.warnings.append(
                "MC2 trace columns are neither root outputs (nnc-sim traces) nor "
                "listed in webots.csv.variables (Webots CSV log): "
                f"{', '.join(untraced)}"
            )
        if not webots_csv.include_step:
            self.warnings.append(
                "webots.csv.include_step is false, but MC2 reads the first trace "
                "column as time; set include_step: true to use the Webots CSV log "
                "with MC2"
            )
        if webots_csv.delimiter not in MC2_TRACE_DELIMITERS:
            self.warnings.append(
                f"webots.csv.delimiter {webots_csv.delimiter!r} cannot be read by "
                'MC2; use " " (or ";" with the MC2 -snoopy option)'
            )

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
