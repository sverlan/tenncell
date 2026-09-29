"""Parser for the Webots-specific YAML section."""

from __future__ import annotations

from ...inputs.yaml.sections import YamlSectionContext
from ...inputs.yaml.errors import YamlLocatedError, as_yaml_located_error
from .webots_config import WebotsBindingConfig, WebotsConfig, WebotsCsvConfig


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
            raise YamlLocatedError(
                f"Webots binding '{variable}' must be a mapping",
                context.source_path,
                context.locations.line_for("webots", "bindings", variable),
            )
        device = item.get("device")
        if not isinstance(device, str):
            raise YamlLocatedError(
                f"Webots binding '{variable}' must define a string 'device'",
                context.source_path,
                context.locations.line_for("webots", "bindings", variable, "device"),
            )
        read_method = item.get("read_method")
        if read_method is not None and not isinstance(read_method, str):
            raise YamlLocatedError(
                f"Webots binding '{variable}' read_method must be a string",
                context.source_path,
                context.locations.line_for(
                    "webots", "bindings", variable, "read_method"
                ),
            )
        write_method = item.get("write_method")
        if write_method is not None and not isinstance(write_method, str):
            raise YamlLocatedError(
                f"Webots binding '{variable}' write_method must be a string",
                context.source_path,
                context.locations.line_for(
                    "webots", "bindings", variable, "write_method"
                ),
            )
        if read_method is None and write_method is None:
            raise YamlLocatedError(
                f"Webots binding '{variable}' must define at least one method",
                context.source_path,
                context.locations.line_for("webots", "bindings", variable),
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
        raise YamlLocatedError(
            "webots.csv must be a mapping if provided",
            context.source_path,
            context.locations.line_for("webots", "csv")
            or context.locations.line_for("webots"),
        )

    file = raw_csv.get("file")
    if not isinstance(file, str):
        raise YamlLocatedError(
            "webots.csv.file must be a string",
            context.source_path,
            context.locations.line_for("webots", "csv", "file")
            or context.locations.line_for("webots", "csv"),
        )

    variables = raw_csv.get("variables")
    if not isinstance(variables, list) or not all(
        isinstance(variable, str) for variable in variables
    ):
        raise YamlLocatedError(
            "webots.csv.variables must be a list of strings",
            context.source_path,
            context.locations.line_for("webots", "csv", "variables")
            or context.locations.line_for("webots", "csv"),
        )

    include_step = raw_csv.get("include_step", False)
    if not isinstance(include_step, bool):
        raise YamlLocatedError(
            "webots.csv.include_step must be a boolean if provided",
            context.source_path,
            context.locations.line_for("webots", "csv", "include_step"),
        )

    include_time = raw_csv.get("include_time", False)
    if not isinstance(include_time, bool):
        raise YamlLocatedError(
            "webots.csv.include_time must be a boolean if provided",
            context.source_path,
            context.locations.line_for("webots", "csv", "include_time"),
        )

    include_initial = raw_csv.get("include_initial", False)
    if not isinstance(include_initial, bool):
        raise YamlLocatedError(
            "webots.csv.include_initial must be a boolean if provided",
            context.source_path,
            context.locations.line_for("webots", "csv", "include_initial"),
        )

    return WebotsCsvConfig(
        file=file,
        variables=variables,
        include_step=include_step,
        include_time=include_time,
        include_initial=include_initial,
    )


def parse_webots_section(
    section: dict | None, context: YamlSectionContext
) -> WebotsConfig:
    """Parse the Webots YAML section into controller generation config."""
    try:
        data = _require_mapping(section)
    except Exception as e:
        raise as_yaml_located_error(
            e,
            context.source_path,
            context.locations.line_for("webots") or context.locations.first_line_under(),
        )
    controller_name = data.get("controller_name", context.source_path.stem)
    if not isinstance(controller_name, str):
        raise YamlLocatedError(
            "webots.controller_name must be a string if provided",
            context.source_path,
            context.locations.line_for("webots", "controller_name"),
        )
    timestep = data.get("timestep")
    if timestep is not None and not isinstance(timestep, int):
        raise YamlLocatedError(
            "webots.timestep must be an integer if provided",
            context.source_path,
            context.locations.line_for("webots", "timestep"),
        )
    try:
        raw_bindings = _require_optional_mapping(data.get("bindings"), "bindings")
    except Exception as e:
        raise as_yaml_located_error(
            e,
            context.source_path,
            context.locations.line_for("webots", "bindings")
            or context.locations.line_for("webots"),
        )
    try:
        raw_init = _require_optional_mapping(data.get("init"), "init")
    except Exception as e:
        raise as_yaml_located_error(
            e,
            context.source_path,
            context.locations.line_for("webots", "init")
            or context.locations.line_for("webots"),
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
