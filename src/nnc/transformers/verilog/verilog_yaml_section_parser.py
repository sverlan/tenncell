"""Parser for the Verilog-specific YAML section."""

from pathlib import Path
from typing import NoReturn

from ...inputs.yaml.resolution import resolve_path
from ...inputs.yaml.errors import YamlLocatedError, as_yaml_located_error
from ...inputs.yaml.locations import YamlLocationIndex, load_yaml_data_and_locations
from ...inputs.yaml.sections import YamlSectionContext
from .hardware_config import (
    ClockConfig,
    ExternalInstance,
    ExternalModuleSchema,
    PortConfig,
    RealEncoding,
    ResetConfig,
    VerilogFixedPointTypeInfo,
    VerilogHardwareConfig,
    VerilogLogicTypeInfo,
    VerilogTypeInfo,
)


def _require_mapping(raw: dict | None, section_name: str) -> dict:
    """Require a mapping for a YAML section and normalize missing values."""
    if raw is None:
        raise ValueError(f"Missing required Verilog section '{section_name}'")
    if not isinstance(raw, dict):
        raise ValueError(f"Verilog section '{section_name}' must be a mapping")
    return raw


def _field_line(locations: YamlLocationIndex | None, *path: object) -> int | None:
    """Look up the most specific available line for a YAML field."""
    if locations is None:
        return None
    line = locations.line_for(*path)
    if line is not None:
        return line
    line = locations.first_line_under(*path)
    if line is not None:
        return line
    return locations.line_for(*path[:1])


def _field_source(locations: YamlLocationIndex | None, *path: object) -> Path | None:
    """Look up the most specific available source file for a YAML field."""
    if locations is None:
        return None
    location = locations.location_for(*path) or locations.location_under(*path)
    if location is not None:
        return location.source_path
    if path:
        location = locations.location_for(*path[:1]) or locations.location_under(
            *path[:1]
        )
        if location is not None:
            return location.source_path
    return locations.source_path


def _raise_field_error(
    message: str,
    locations: YamlLocationIndex | None,
    *path: object,
) -> NoReturn:
    """Raise a plain or located field error depending on available metadata."""
    if locations is None:
        raise ValueError(message)
    raise YamlLocatedError(
        message,
        _field_source(locations, *path),
        _field_line(locations, *path),
    )


def _signed_field(
    data: dict,
    label: str,
    locations: YamlLocationIndex | None,
    *path: object,
) -> bool:
    """Return the ``signed`` flag, which must be a YAML boolean (default false)."""
    value = data.get("signed", False)
    if not isinstance(value, bool):
        _raise_field_error(
            f"{label} 'signed' must be true or false", locations, *path, "signed"
        )
    return value


def parse_real_encoding(
    raw: dict | None,
    locations: YamlLocationIndex | None = None,
) -> RealEncoding:
    """Parse the Verilog fixed-point encoding description."""
    data = _require_mapping(raw, "real_encoding")
    missing = [
        key for key in ("kind", "signed", "width", "frac_bits") if key not in data
    ]
    if missing:
        _raise_field_error(
            f"verilog.real_encoding is missing required field(s): {', '.join(missing)}",
            locations,
            "verilog",
            "real_encoding",
        )
    return RealEncoding(
        kind=data["kind"],
        signed=_signed_field(
            data, "verilog.real_encoding", locations, "verilog", "real_encoding"
        ),
        width=data["width"],
        frac_bits=data["frac_bits"],
    )


def _parse_port_item(
    name: str,
    raw_port: dict,
    locations: YamlLocationIndex | None = None,
    *path: object,
) -> PortConfig:
    """Parse one port description into a config object."""
    data = _require_mapping(raw_port, "port")
    if "direction" not in data:
        _raise_field_error(
            "verilog port is missing required field 'direction'",
            locations,
            *path,
        )
    return PortConfig(
        name=data.get("name", name),
        dir=data["direction"],
        kind=data.get("kind", "logic"),
        width=data.get("width", 1),
        signed=_signed_field(data, f"verilog port '{name}'", locations, *path),
        rename=data.get("rename"),
    )


def _parse_type_item(
    name: str,
    raw_type: dict,
    locations: YamlLocationIndex | None = None,
    *path: object,
) -> VerilogTypeInfo:
    """Parse one internal Verilog type hint into a config object."""
    data = _require_mapping(raw_type, "type")
    if "kind" not in data:
        _raise_field_error(
            "verilog.types entry is missing required field 'kind'",
            locations,
            *path,
            "kind",
        )
    kind = data["kind"]
    if kind == "logic":
        if "width" not in data:
            _raise_field_error(
                "verilog.types entry with kind 'logic' is missing required field 'width'",
                locations,
                *path,
                "width",
            )
        return VerilogLogicTypeInfo(
            kind="logic",
            width=data["width"],
            signed=_signed_field(data, f"verilog.types '{name}'", locations, *path),
        )
    if kind == "fixed_point":
        missing = [key for key in ("width", "frac_bits") if key not in data]
        if missing:
            _raise_field_error(
                "verilog.types entry with kind 'fixed_point' is missing required field(s): "
                f"{', '.join(missing)}",
                locations,
                *path,
            )
        return VerilogFixedPointTypeInfo(
            kind="fixed_point",
            width=data["width"],
            frac_bits=data["frac_bits"],
            signed=_signed_field(data, f"verilog.types '{name}'", locations, *path),
        )
    _raise_field_error(
        f"verilog.types entry '{name}' has unsupported kind '{kind}'",
        locations,
        *path,
        "kind",
    )


def parse_types(
    raw_types: dict | None,
    locations: YamlLocationIndex | None = None,
    *path: object,
) -> tuple[dict[str, VerilogTypeInfo], dict[str, int | None]]:
    """Parse the Verilog internal typing hints into config objects."""
    types: dict[str, VerilogTypeInfo] = {}
    lines: dict[str, int | None] = {}
    if raw_types is None:
        return types, lines
    data = _require_mapping(raw_types, "types")
    for name, item in data.items():
        types[name] = _parse_type_item(name, item, locations, *path, name)
        lines[name] = locations.line_for(*path, name) if locations is not None else None
    return types, lines


def parse_ports(
    raw_ports: dict | list[dict] | None,
    locations: YamlLocationIndex | None = None,
    *path: object,
) -> list[PortConfig]:
    """Parse the Verilog port list into config objects."""
    ports = []
    if isinstance(raw_ports, dict):
        for name, item in raw_ports.items():
            ports.append(_parse_port_item(name, item, locations, *path, name))
        return ports

    for index, item in enumerate(raw_ports or []):
        ports.append(
            _parse_port_item(item.get("name", ""), item, locations, *path, index)
        )
    return ports


def parse_external_schema(
    raw: dict | None,
    file_path: Path | None = None,
    locations: YamlLocationIndex | None = None,
    *path: object,
) -> ExternalModuleSchema:
    """Parse a reusable external module schema."""
    data = _require_mapping(raw, "schema")
    if "module" not in data and "name" not in data:
        _raise_field_error(
            "external schema is missing required field 'module'",
            locations,
            *path,
            "module",
        )
    module_name = data.get("module", data.get("name"))
    source_path = str(file_path) if file_path is not None else None
    return ExternalModuleSchema(
        module=module_name,
        parameters=data.get("parameters", {}),
        ports=parse_ports(data.get("ports"), locations, *path, "ports"),
        source_path=source_path,
    )


def parse_verilog_config(
    verilog_data: dict | None,
    legacy_module_data: dict | None = None,
    locations: YamlLocationIndex | None = None,
) -> VerilogHardwareConfig:
    """Parse the Verilog section, including legacy module-based input."""
    data = verilog_data or {}
    legacy = legacy_module_data or {}
    source = data if verilog_data is not None else legacy
    clock_data = source.get("clock")
    if clock_data is None:
        clock_name = "clk"
    elif isinstance(clock_data, str):
        clock_name = clock_data
    else:
        _raise_field_error(
            "verilog.clock must be a string",
            locations,
            "verilog",
            "clock",
        )
    reset_data = source.get("reset")
    if reset_data is None:
        reset_name = "rst"
        active_high = True
    elif isinstance(reset_data, str):
        reset_name = reset_data
        active_high = True
    else:
        _raise_field_error(
            "verilog.reset must be a string",
            locations,
            "verilog",
            "reset",
        )
    types, type_lines = parse_types(source.get("types"), locations, "verilog", "types")
    return VerilogHardwareConfig(
        real_encoding=parse_real_encoding(source.get("real_encoding"), locations)
        if "real_encoding" in source
        else None,
        clock=ClockConfig(name=clock_name),
        reset=ResetConfig(name=reset_name, active_high=active_high),
        ports=parse_ports(source.get("ports"), locations, "verilog", "ports"),
        types=types,
        type_lines=type_lines,
    )


def parse_verilog_section(
    section: dict | None, context: YamlSectionContext
) -> VerilogHardwareConfig:
    """Parse a registered Verilog YAML section into hardware config."""
    try:
        config = parse_verilog_config(
            section, context.raw_data.get("module"), context.locations
        )
    except Exception as e:
        source_path = _field_source(context.locations, "verilog")
        raise as_yaml_located_error(
            e,
            source_path,
            context.locations.line_for("verilog")
            or context.locations.first_line_under(),
        )
    source = section or {}
    external_entries = source.get("externals", context.raw_data.get("externals", {}))
    if not isinstance(external_entries, dict):
        raise context.locations.error(
            "verilog.externals must be a mapping of instance aliases",
            "verilog",
            "externals",
        )
    for alias, external_data in external_entries.items():
        if not isinstance(external_data, dict):
            raise context.locations.error(
                "verilog.externals entries must be mappings",
                "verilog",
                "externals",
                alias,
            )
        definition: ExternalModuleSchema
        header_path = external_data.get("header")
        schema_data = external_data.get("schema")
        if header_path is not None:
            resolved_header = resolve_path(
                header_path, context.source_path, context.import_paths
            )
            if resolved_header not in context.header_cache:
                try:
                    context.header_cache[resolved_header] = parse_external_header(
                        resolved_header
                    )
                except Exception as e:
                    raise as_yaml_located_error(
                        YamlLocatedError(
                            f"Error parsing external header '{header_path}':\n{e}",
                            context.locations.source_for(
                                "verilog", "externals", alias, "header"
                            ),
                            context.locations.line_for(
                                "verilog", "externals", alias, "header"
                            ),
                        )
                    )
            definition = context.header_cache[resolved_header]
            header_value: str | None = str(resolved_header)
            schema_value: dict | None = None
        elif schema_data is not None:
            try:
                definition = parse_external_schema(
                    schema_data,
                    None,
                    context.locations,
                    "verilog",
                    "externals",
                    alias,
                    "schema",
                )
            except Exception as e:
                source_path = _field_source(
                    context.locations,
                    "verilog",
                    "externals",
                    alias,
                    "schema",
                )
                raise as_yaml_located_error(
                    e,
                    source_path,
                    context.locations.line_for("verilog", "externals", alias, "schema")
                    or context.locations.line_for("verilog", "externals", alias)
                    or context.locations.line_for("verilog"),
                )
            header_value = None
            schema_value = schema_data
        else:
            raise context.locations.error(
                "verilog.externals entries must define either 'header' or 'schema'",
                "verilog",
                "externals",
                alias,
            )
        config.externals.append(
            ExternalInstance(
                alias=alias,
                header=header_value,
                schema=schema_value,
                parameters=external_data.get("parameters", {}),
                connections=external_data.get("connections", {}),
                definition=definition,
            )
        )
    return config


def parse_external_header(file_path: Path) -> ExternalModuleSchema:
    """Parse an external module header file into a config object."""
    data, locations = load_yaml_data_and_locations(file_path)
    schema_data = data.get("schema")
    if not schema_data:
        raise YamlLocatedError(
            "External header must contain a 'schema' section",
            file_path,
            locations.line_for("schema") or locations.first_line_under(),
        )
    try:
        return parse_external_schema(
            schema_data,
            file_path,
            locations,
            "schema",
        )
    except Exception as e:
        raise as_yaml_located_error(
            e,
            file_path,
            locations.line_for("schema") or locations.first_line_under(),
        )
