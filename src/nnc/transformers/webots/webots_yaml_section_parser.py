"""Parser for the Webots-specific YAML section."""

from __future__ import annotations

import keyword
import textwrap
from pathlib import Path, PurePosixPath, PureWindowsPath

from ...csv_format import validate_csv_delimiter, validate_csv_precision
from ...inputs.yaml.sections import YamlSectionContext
from ...inputs.yaml.errors import YamlLocatedError, as_yaml_located_error
from .webots_config import (
    CODE_POINTS,
    WebotsBindingConfig,
    WebotsCodeBlock,
    WebotsConfig,
    WebotsCsvConfig,
)


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
    warnings: list[str],
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
        # Without a device, webots.code.setup provides devices[variable].
        # Only a missing key means virtual; `device: null` is an error.
        device = item.get("device")
        if "device" in item and (not isinstance(device, str) or not device):
            raise context.locations.error(
                f"Webots binding '{variable}' device must be a non-empty string "
                "(leave it out for a virtual device provided by webots.code.setup)",
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
        # The controller emits `devices[...].<method>(...)`. A method name is
        # the normal case; other text (an expression) is pasted unchecked,
        # with a warning pointing to webots.code. Empty
        # text or a lone keyword could never work: errors.
        for key, method in (
            ("read_method", read_method),
            ("write_method", write_method),
        ):
            if method is None or (
                method.isidentifier() and not keyword.iskeyword(method)
            ):
                continue
            if not method.strip() or keyword.iskeyword(method.strip()):
                raise context.locations.error(
                    f"Webots binding '{variable}' {key} must be a method name, "
                    f"not {method!r}",
                    "webots",
                    "bindings",
                    variable,
                    key,
                )
            source, line = _field_location(context, "webots", "bindings", variable, key)
            where = f"{source}:{line}: " if line is not None else ""
            warnings.append(
                f"{where}Webots binding '{variable}' {key} is not a method name; "
                "the text is pasted into the controller unchecked. Prefer a "
                "method added to the device in webots.code.setup"
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


def _parse_code(
    raw_code: object, context: YamlSectionContext
) -> dict[str, WebotsCodeBlock]:
    """Parse ``webots.code``: inline text or ``{file: PATH}`` per point.

    A file path is relative to the YAML file that declares it (an include
    fragment, possibly); the file is read here, never imported or run.
    """
    if raw_code is None:
        return {}
    if not isinstance(raw_code, dict):
        raise context.locations.error(
            "webots.code must be a mapping if provided", "webots", "code"
        )
    code: dict[str, WebotsCodeBlock] = {}
    for point, value in raw_code.items():
        path = ("webots", "code", point)
        if point not in CODE_POINTS:
            raise context.locations.error(
                f"unknown webots.code insertion point {point!r}; expected one of "
                + ", ".join(CODE_POINTS),
                *path,
            )
        if isinstance(value, str):
            text, source = value, "inline"
        elif isinstance(value, dict) and set(value) == {"file"}:
            file_name = value["file"]
            if not isinstance(file_name, str) or not file_name.strip():
                raise context.locations.error(
                    f"webots.code.{point}.file must be a non-empty string",
                    *path,
                    "file",
                )
            # A drive or root (C:\x.py, /x.py, \\host\share) would discard the
            # folder of the declaring file: only relative paths are portable.
            # Both syntaxes are checked, whatever the host system.
            if PureWindowsPath(file_name).anchor or PurePosixPath(file_name).anchor:
                raise context.locations.error(
                    f"webots.code.{point}.file must be relative to the YAML file "
                    f"that declares it, not {file_name!r}",
                    *path,
                    "file",
                )
            declared_in = context.locations.source_for_under(*path)
            file_path = Path(declared_in).parent / file_name
            try:
                # utf-8-sig: a BOM would end up inside the controller.
                text = file_path.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeDecodeError) as error:
                raise context.locations.error(
                    f"webots.code.{point}: cannot read {file_path} ({error})",
                    *path,
                    "file",
                ) from error
            source = file_name
        else:
            raise context.locations.error(
                f"webots.code.{point} must be a string or a mapping with only 'file'",
                *path,
            )
        # Relative indentation is kept; leading and trailing blank lines go.
        text = textwrap.dedent(text.replace("\r\n", "\n")).lstrip("\n").rstrip()
        if text:
            code[point] = WebotsCodeBlock(text=text, source=source)
    return code


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
    warnings: list[str] = []
    bindings = _parse_bindings(raw_bindings, context, warnings)
    init = _parse_init(raw_init)
    csv = _parse_csv(data.get("csv"), context)
    code = _parse_code(data.get("code"), context)
    return WebotsConfig(
        controller_name=controller_name,
        timestep=timestep,
        bindings=bindings,
        init=init,
        csv=csv,
        code=code,
        warnings=warnings,
        where=_where(context, bindings, init),
    )


def _where(
    context: YamlSectionContext,
    bindings: dict[str, WebotsBindingConfig],
    init: dict[str, object],
) -> dict[tuple[str, ...], str]:
    """``"file:line: "`` of the YAML paths the transformer reports errors on."""
    paths: list[tuple[str, ...]] = [
        (),
        ("bindings",),
        *(("bindings", variable) for variable in bindings),
        ("init",),
        *(("init", variable) for variable in init),
        ("csv", "variables"),
    ]
    where: dict[tuple[str, ...], str] = {}
    for path in paths:
        source, line = _field_location(context, "webots", *path)
        if line is not None:
            where[path] = f"{source}:{line}: "
    return where
