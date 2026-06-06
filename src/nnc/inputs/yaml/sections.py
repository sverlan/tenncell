"""Backend section parsing support for YAML inputs."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .locations import YamlLocationIndex


@dataclass(slots=True)
class YamlSectionContext:
    """Context available to backend-specific YAML section parsers."""

    source_path: Path
    import_paths: list[Path]
    header_cache: dict[Path, object]
    raw_data: dict[str, Any]
    locations: YamlLocationIndex


SectionParser = Callable[[dict | None, YamlSectionContext], object]


def parse_registered_sections(
    data: dict[str, Any],
    context: YamlSectionContext,
    parsers: dict[str, SectionParser],
) -> dict[str, object]:
    return {name: parser(data.get(name), context) for name, parser in parsers.items()}
