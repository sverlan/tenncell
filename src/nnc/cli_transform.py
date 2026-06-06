"""CLI tool for transforming TENNCell systems to various output formats."""

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, Type

from nnc.inputs.yaml.sections import YamlSectionContext, parse_registered_sections
from nnc.inputs.yaml.locations import YamlLocationIndex
from nnc.model.system import NncSystem
from nnc.transformers import (
    BaseTransformer,
    PythonTransformer,
    VerilogTransformer,
    WebotsTransformer,
)
from nnc.transformers.webots.webots_yaml_section_parser import parse_webots_section
from nnc.transformers.verilog.verilog_yaml_section_parser import parse_verilog_section
from nnc._version import __version__


# Registry of available transformers
TRANSFORMERS: Dict[str, Type[BaseTransformer]] = {
    "python": PythonTransformer,
    "verilog": VerilogTransformer,
    "webots": WebotsTransformer,
}


def get_transformer(transform_type: str) -> BaseTransformer:
    """Get a transformer instance by type name.

    Args:
        transform_type: The type of transformer to create

    Returns:
        Transformer instance

    Raises:
        ValueError: If transform_type is not supported
    """
    if transform_type not in TRANSFORMERS:
        available = ", ".join(TRANSFORMERS.keys())
        raise ValueError(
            f"Unsupported transformation type '{transform_type}'. Available types: {available}"
        )

    return TRANSFORMERS[transform_type]()


def main():
    """Main entry point for the ``nnc-gen`` CLI."""
    parser = argparse.ArgumentParser(
        description=f"TENNCell Transformer v{__version__} - Convert TENNCell systems to various output formats",
        prog="nnc-gen",
    )

    parser.add_argument(
        "system_files", nargs="+", help="TENNCell system files (.yaml) to transform"
    )

    parser.add_argument(
        "-t",
        "--type",
        dest="transform_type",
        required=True,
        choices=list(TRANSFORMERS.keys()),
        help="Transformation type",
    )

    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("."),
        help="Output directory for transformed files (default: current directory)",
    )

    parser.add_argument(
        "--output-suffix",
        default="",
        help="Suffix to add to output filenames (before extension)",
    )

    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )
    parser.add_argument(
        "--import-path",
        action="append",
        default=[],
        help="Additional directory to search for imported TENNCell files and external headers",
    )
    parser.add_argument(
        "--import-paths",
        default="",
        help="Path-separated list of additional import directories",
    )

    args = parser.parse_args()

    # Ensure output directory exists
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Get transformer
    try:
        transformer = get_transformer(args.transform_type)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    extra_import_paths = list(args.import_path)
    if args.import_paths:
        extra_import_paths.extend(
            [path for path in args.import_paths.split(os.pathsep) if path]
        )

    # Process each file
    had_error = False
    for nnc_file_path in args.system_files:
        nnc_file = Path(nnc_file_path)

        if not nnc_file.exists():
            print(f"Error: File '{nnc_file}' not found", file=sys.stderr)
            had_error = True
            continue

        if args.verbose:
            print(f"Processing: {nnc_file}")

        try:
            # Load TENNCell system
            raw_data_cache = {}
            nnc_system = NncSystem.from_yaml(
                str(nnc_file),
                import_paths=extra_import_paths,
                _raw_data_cache=raw_data_cache,
            )

            # Verilog emits one file per module in the import closure.
            # Python and Webots emit one composed file for the root system only.
            if args.transform_type == "verilog":
                systems_to_emit = _collect_import_closure(nnc_system)
                assert isinstance(transformer, VerilogTransformer)
                transformer.set_verilog_configs(
                    _parse_verilog_configs(
                        systems_to_emit, raw_data_cache, extra_import_paths
                    )
                )
            elif args.transform_type == "webots":
                assert isinstance(transformer, WebotsTransformer)
                transformer.set_webots_configs(
                    _parse_webots_configs([nnc_system], raw_data_cache)
                )
                systems_to_emit = [nnc_system]
            else:
                systems_to_emit = [nnc_system]
            for system in systems_to_emit:
                transformed_code = transformer.transform(system)
                source_path = (
                    getattr(system, "__dict__", {}).get("source_path") or nnc_file
                )
                base_name = source_path.stem
                if args.output_suffix:
                    base_name += args.output_suffix

                output_file = args.output_dir / (
                    base_name + transformer.get_file_extension()
                )

                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(transformed_code)

                if args.verbose:
                    print(f"  -> {output_file}")

        except Exception as e:
            print(f"Error processing '{nnc_file}': {e}", file=sys.stderr)
            had_error = True
            if args.verbose:
                import traceback

                traceback.print_exc()
            continue

    if args.verbose:
        print("Transformation complete.")
    if had_error:
        return 1
    return 0


def _collect_import_closure(root: NncSystem) -> list[NncSystem]:
    seen: set[str] = set()
    ordered: list[NncSystem] = []

    def visit(system: NncSystem):
        source_key = str(getattr(system, "source_path", None) or id(system))
        if source_key in seen:
            return
        seen.add(source_key)
        imports = getattr(system, "__dict__", {}).get("imports", [])
        for item in imports or []:
            if getattr(item, "system", None) is not None:
                visit(item.system)
        ordered.append(system)

    visit(root)
    return ordered


def _parse_verilog_configs(
    systems: list[NncSystem],
    raw_data_cache: dict[Path, dict],
    import_paths: list[str],
):
    configs = {}
    header_cache: dict[Path, object] = {}
    import_paths_resolved = [Path(path).resolve() for path in import_paths]
    for system in systems:
        if system.source_path is None:
            raise ValueError("Verilog export requires systems loaded from YAML files")
        data = raw_data_cache[system.source_path]
        context = YamlSectionContext(
            source_path=system.source_path,
            import_paths=import_paths_resolved,
            header_cache=header_cache,
            raw_data=data,
            locations=system.source_locations
            or YamlLocationIndex(system.source_path, {}),
        )
        parsed = parse_registered_sections(
            data, context, {"verilog": parse_verilog_section}
        )
        configs[system.source_path] = parsed["verilog"]
    return configs


def _parse_webots_configs(
    systems: list[NncSystem],
    raw_data_cache: dict[Path, dict],
):
    configs = {}
    for system in systems:
        if system.source_path is None:
            raise ValueError("Webots export requires systems loaded from YAML files")
        data = raw_data_cache[system.source_path]
        context = YamlSectionContext(
            source_path=system.source_path,
            import_paths=[],
            header_cache={},
            raw_data=data,
            locations=system.source_locations
            or YamlLocationIndex(system.source_path, {}),
        )
        parsed = parse_registered_sections(
            data, context, {"webots": parse_webots_section}
        )
        configs[system.source_path] = parsed["webots"]
    return configs


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"Error: {e}")
