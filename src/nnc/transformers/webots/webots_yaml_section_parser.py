"""Parser for the Webots-specific YAML section."""

from __future__ import annotations

from ...csv_format import validate_csv_delimiter, validate_csv_precision
from ...inputs.yaml.sections import YamlSectionContext
from ...inputs.yaml.errors import YamlLocatedError, as_yaml_located_error
from .webots_config import WebotsBindingConfig, WebotsConfig, WebotsCsvConfig


def _field_location(context: YamlSectionContext, *path: object):
    """Return origin-aware source and line for wrapping plain exceptions."""
    location = context.locations.location_for(
        *path
    ) or context.locations.location_under(*path)
    if location is None:
        return context.source_path, None
    return location.source_path, location.line


def _require_mapping(raw: dict | None) -> dict:
    if raw is None:
        raise ValueError("Missing required Webots section 'webots'")
    if not isinstance(raw, dict):
        raise ValueError("Webots section 'webots' must be a mapping")
    return raw


def _require_optional_mapping(raw: object, field_name: str) -> dict:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"webots.{field_name} must be a mapping if provided")
    return raw


def _normalize_init_value(value: object) -> object:
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"inf", "+inf", ".inf", "+.inf"}:
            return float("inf")
        if normalized in {"-inf", "-.inf"}:
            return float("-inf")
        if normalized in {"nan", ".nan"}:
            return float("nan")
    return value


def _parse_bindings(
    raw_bindings: dict[str, dict] | None,
    context: YamlSectionContext,
) -> dict[str, WebotsBindingConfig]:
    bindings: dict[str, WebotsBindingConfig] = {}
    for variable, item in (raw_bindings or {}).items():
        if not isinstance(item, dict):
            raise context.locations.error(
                f"Webots binding '{variable}' must be a mapping",
                "webots",
                "bindings",
                variable,
            )
        device = item.get("device")
        if not isinstance(device, str):
            raise context.locations.error(
                f"Webots binding '{variable}' must define a string 'device'",
                "webots",
                "bindings",
                variable,
                "device",
            )
        read_method = item.get("read_method")
        if read_method is not None and not isinstance(read_method, str):
            raise context.locations.error(
                f"Webots binding '{variable}' read_method must be a string",
                "webots",
                "bindings",
                variable,
                "read_method",
            )
        write_method = item.get("write_method")
        if write_method is not None and not isinstance(write_method, str):
            raise context.locations.error(
                f"Webots binding '{variable}' write_method must be a string",
                "webots",
                "bindings",
                variable,
                "write_method",
            )
        if read_method is None and write_method is None:
            raise context.locations.error(
                f"Webots binding '{variable}' must define at least one method",
                "webots",
                "bindings",
                variable,
            )
        bindings[variable] = WebotsBindingConfig(
            device=device,
            read_method=read_method,
            write_method=write_method,
        )
    return bindings


def _parse_init(raw_init: dict[str, object] | None) -> dict[str, object]:
    return {
        variable: _normalize_init_value(value)
        for variable, value in (raw_init or {}).items()
    }


def _parse_csv(raw_csv: object, context: YamlSectionContext) -> WebotsCsvConfig | None:
    if raw_csv is None:
        return None
    if not isinstance(raw_csv, dict):
        raise context.locations.error(
            "webots.csv must be a mapping if provided",
            "webots",
            "csv",
        )

    file = raw_csv.get("file")
    if not isinstance(file, str):
        raise context.locations.error(
            "webots.csv.file must be a string",
            "webots",
            "csv",
            "file",
        )

    variables = raw_csv.get("variables")
    if not isinstance(variables, list) or not all(
        isinstance(variable, str) for variable in variables
    ):
        raise context.locations.error(
            "webots.csv.variables must be a list of strings",
            "webots",
            "csv",
            "variables",
        )

    include_step = raw_csv.get("include_step", False)
    if not isinstance(include_step, bool):
        raise context.locations.error(
            "webots.csv.include_step must be a boolean if provided",
            "webots",
            "csv",
            "include_step",
        )

    include_time = raw_csv.get("include_time", False)
    if not isinstance(include_time, bool):
        raise context.locations.error(
            "webots.csv.include_time must be a boolean if provided",
            "webots",
            "csv",
            "include_time",
        )

    include_initial = raw_csv.get("include_initial", False)
    if not isinstance(include_initial, bool):
        raise context.locations.error(
            "webots.csv.include_initial must be a boolean if provided",
            "webots",
            "csv",
            "include_initial",
        )

    try:
        delimiter = validate_csv_delimiter(
            raw_csv.get("delimiter", ","), field_name="webots.csv.delimiter"
        )
    except ValueError as e:
        source_path, line = _field_location(context, "webots", "csv", "delimiter")
        raise YamlLocatedError(
            str(e),
            source_path,
            line,
        ) from e

    try:
        precision = validate_csv_precision(
            raw_csv.get("precision"), field_name="webots.csv.precision"
        )
    except ValueError as e:
        source_path, line = _field_location(context, "webots", "csv", "precision")
        raise YamlLocatedError(
            str(e),
            source_path,
            line,
        ) from e

    return WebotsCsvConfig(
        file=file,
        variables=variables,
        include_step=include_step,
        include_time=include_time,
        include_initial=include_initial,
        delimiter=delimiter,
        precision=precision,
    )


def parse_webots_section(
    section: dict | None, context: YamlSectionContext
) -> WebotsConfig:
    """Parse the Webots YAML section into controller generation config."""
    try:
        data = _require_mapping(section)
    except Exception as e:
        source_path, line = _field_location(context, "webots")
        raise as_yaml_located_error(
            e,
            source_path,
            line,
        )
    controller_name = data.get("controller_name", context.source_path.stem)
    if not isinstance(controller_name, str):
        raise context.locations.error(
            "webots.controller_name must be a string if provided",
            "webots",
            "controller_name",
        )
    timestep = data.get("timestep")
    if timestep is not None and not isinstance(timestep, int):
        raise context.locations.error(
            "webots.timestep must be an integer if provided",
            "webots",
            "timestep",
        )
    try:
        raw_bindings = _require_optional_mapping(data.get("bindings"), "bindings")
    except Exception as e:
        source_path, line = _field_location(context, "webots", "bindings")
        raise as_yaml_located_error(
            e,
            source_path,
            line,
        )
    try:
        raw_init = _require_optional_mapping(data.get("init"), "init")
    except Exception as e:
        source_path, line = _field_location(context, "webots", "init")
        raise as_yaml_located_error(
            e,
            source_path,
            line,
        )
    bindings = _parse_bindings(raw_bindings, context)
    init = _parse_init(raw_init)
    csv = _parse_csv(data.get("csv"), context)
    return WebotsConfig(
        controller_name=controller_name,
        timestep=timestep,
        bindings=bindings,
        init=init,
        csv=csv,
    )
