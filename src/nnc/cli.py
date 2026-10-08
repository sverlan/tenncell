import argparse
import csv
import sys
from contextlib import ExitStack
from pathlib import Path

from nnc.csv_format import (
    CsvFormatConfig,
    format_csv_value,
    validate_csv_delimiter,
    validate_csv_precision,
)
from nnc.model.system import NncSystem

from nnc._version import __version__


def main() -> int:
    """Run the TENNCell simulator CLI and return a process-style exit code."""
    try:
        return _run()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _run() -> int:
    """Parse arguments, run the simulator, and return ``0`` on success."""
    parser = argparse.ArgumentParser(
        description=f"TENNCell simulator v{__version__}", prog="nnc-sim"
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"nnc-sim {__version__}",
    )
    parser.add_argument(
        "system_file",
        type=Path,
        help="The file containing the description of the TENNCell system",
    )
    parser.add_argument(
        "input",
        type=Path,
        nargs="?",
        default=None,
        help="Input (CSV) file giving stimulus for each step (default: stdin)",
    )
    parser.add_argument(
        "output",
        type=Path,
        nargs="?",
        default=None,
        help="Output (CSV) file giving the results of each step (default: stdout)",
    )
    parser.add_argument(
        "-c",
        "--compute_mode",
        action="store_true",
        help="Run in continuous compute mode (default: False)",
    )
    parser.add_argument(
        "-s", "--steps", type=int, default=1, help="Number of steps to run (default: 1)"
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="Output in CSV format when in continuous compute mode",
    )
    parser.add_argument(
        "--csv-include-initial",
        action="store_true",
        help="Write an initial state row before consuming CSV input in IO mode",
    )
    parser.add_argument(
        "--csv-include-step",
        action="store_true",
        help="Prepend a step column to IO-mode CSV output (initial row is step 0)",
    )
    parser.add_argument(
        "--csv-no-initial",
        action="store_true",
        help="Suppress the initial state row in continuous CSV compute mode",
    )
    parser.add_argument(
        "--csv-delimiter",
        default=",",
        help="CSV delimiter used for input and output files (default: comma)",
    )
    parser.add_argument(
        "--csv-precision",
        type=int,
        default=None,
        help="Format numeric CSV output with this many decimal places",
    )
    args = parser.parse_args()
    csv_config = CsvFormatConfig(
        delimiter=validate_csv_delimiter(args.csv_delimiter),
        precision=validate_csv_precision(args.csv_precision),
    )

    with ExitStack() as stack:
        input_handle = (
            sys.stdin
            if args.input is None
            else stack.enter_context(args.input.open("r", encoding="utf-8", newline=""))
        )
        output_handle = (
            sys.stdout
            if args.output is None
            else stack.enter_context(
                args.output.open("w", encoding="utf-8", newline="")
            )
        )
        nnc = NncSystem.from_yaml(str(args.system_file))

        if args.compute_mode:
            if len(nnc.input_variables) > 0:
                raise ValueError(
                    "Cannot run in continuous compute mode with input variables"
                )
            if args.csv:
                # CSV output mode
                result = {
                    name: format_csv_value(variable.value, csv_config.precision)
                    for name, variable in nnc.output_variables.items()
                }
                fieldnames = ["step"] + list(result.keys())
                writer = csv.DictWriter(
                    output_handle,
                    fieldnames=fieldnames,
                    delimiter=csv_config.delimiter,
                    lineterminator="\n",
                )
                writer.writeheader()
                csv_config.include_initial = not args.csv_no_initial
                if csv_config.include_initial:
                    # Write initial state (step 0) with only output variables
                    row = {"step": 0}
                    row.update(result)
                    writer.writerow(row)
                for i in range(args.steps):
                    nnc.step()
                    result = {
                        name: format_csv_value(variable.value, csv_config.precision)
                        for name, variable in nnc.output_variables.items()
                    }
                    row = {"step": i + 1}
                    row.update(result)
                    writer.writerow(row)
            else:
                rows = [_compute_json_row(0, nnc)]
                for i in range(args.steps):
                    nnc.step()
                    rows.append(_compute_json_row(i + 1, nnc))
                _write_compute_json_rows(output_handle, args.steps, rows)
        else:  # IO mode
            reader = csv.DictReader(input_handle, delimiter=csv_config.delimiter)
            fieldnames = (["step"] if args.csv_include_step else []) + list(
                nnc.output_variables.keys()
            )
            writer = None
            csv_config.include_initial = args.csv_include_initial
            if csv_config.include_initial:
                writer = _io_writer(output_handle, fieldnames, csv_config.delimiter)
                writer.writerow(
                    _io_row(nnc, 0, args.csv_include_step, csv_config.precision)
                )

            for step, csv_row in enumerate(reader, start=1):
                if writer is None:
                    writer = _io_writer(output_handle, fieldnames, csv_config.delimiter)

                inputs = {}
                for input_var_name, input_var_value in csv_row.items():
                    if input_var_name not in nnc.input_variables.keys():
                        raise ValueError(f"Unknown input variable {input_var_name}")
                    inputs[input_var_name] = float(input_var_value)

                nnc.step(inputs)

                writer.writerow(
                    _io_row(nnc, step, args.csv_include_step, csv_config.precision)
                )
    return 0


def _io_writer(output_handle, fieldnames: list[str], delimiter: str) -> csv.DictWriter:
    """Create the IO-mode CSV writer and write its header."""
    writer = csv.DictWriter(
        output_handle,
        fieldnames=fieldnames,
        delimiter=delimiter,
        lineterminator="\n",
    )
    writer.writeheader()
    return writer


def _io_row(
    nnc: NncSystem, step: int, include_step: bool, precision: int | None
) -> dict[str, object]:
    """Return one IO-mode CSV row, optionally starting with the step index."""
    row: dict[str, object] = {"step": step} if include_step else {}
    row.update(
        {
            name: format_csv_value(variable.value, precision)
            for name, variable in nnc.output_variables.items()
        }
    )
    return row


def _compute_json_row(step: int, nnc: NncSystem) -> dict[str, float | int]:
    """Return one flat compute-mode JSON output row."""
    row: dict[str, float | int] = {"Step": step}
    row.update(
        {name: variable.value.value for name, variable in nnc.output_variables.items()}
    )
    return row


def _write_compute_json_rows(
    output_handle, steps: int, rows: list[dict[str, float | int]]
) -> None:
    """Write compute-mode JSON with one row object per line."""
    print("[", file=output_handle)
    print(
        f'{{"Message": "Running in continuous compute mode for {steps} steps"}},',
        file=output_handle,
    )
    for index, row in enumerate(rows):
        suffix = "," if index + 1 < len(rows) else ""
        print(f"{_format_compute_json_row(row)}{suffix}", file=output_handle)
    print("]", file=output_handle)


def _format_compute_json_row(row: dict[str, float | int]) -> str:
    """Format one flat compute-mode JSON row."""
    items = ", ".join(f'"{key}": {value}' for key, value in row.items())
    return "{" + items + "}"


if __name__ == "__main__":
    sys.exit(main())
