import argparse
import csv
import sys
from contextlib import ExitStack
from pathlib import Path

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
    args = parser.parse_args()

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
                    name: str(variable.value)
                    for name, variable in nnc.output_variables.items()
                }
                fieldnames = ["step"] + list(result.keys())
                writer = csv.DictWriter(
                    output_handle, fieldnames=fieldnames, lineterminator="\n"
                )
                writer.writeheader()
                # Write initial state (step 0) with only output variables
                row = {"step": 0}
                row.update(result)
                writer.writerow(row)
                for i in range(args.steps):
                    nnc.step()
                    result = {
                        name: str(variable.value)
                        for name, variable in nnc.output_variables.items()
                    }
                    row = {"step": i + 1}
                    row.update(result)
                    writer.writerow(row)
            else:
                print(
                    f"Running in continuous compute mode for {args.steps} steps",
                    file=output_handle,
                )
                result = {
                    name: str(variable.value)
                    for name, variable in nnc.output_variables.items()
                }
                print(f"Step: 0: {result}", file=output_handle)
                for i in range(args.steps):
                    nnc.step()
                    result = {
                        name: str(variable.value)
                        for name, variable in nnc.output_variables.items()
                    }
                    print(f"Step: {i + 1}: {result}", file=output_handle)
        else:  # IO mode
            reader = csv.DictReader(input_handle)
            writer = None

            for csv_row in reader:
                inputs = {}
                for input_var_name, input_var_value in csv_row.items():
                    if input_var_name not in nnc.input_variables.keys():
                        raise ValueError(f"Unknown input variable {input_var_name}")
                    inputs[input_var_name] = float(input_var_value)

                nnc.step(inputs)

                result = {
                    name: variable.value
                    for name, variable in nnc.output_variables.items()
                }

                if writer is None:
                    writer = csv.DictWriter(
                        output_handle,
                        fieldnames=result.keys(),
                        lineterminator="\n",
                    )
                    writer.writeheader()
                writer.writerow(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
