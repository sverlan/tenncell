"""CSV command-line script emission for generated Python TENNCell systems."""

from ...model.system import NncSystem


class PythonCsvScriptEmitter:
    """Emit the CSV executable wrapper around generated Python TENNCell systems."""

    def _emit_format_float_function(self):
        """Emit a helper that formats numeric CSV output consistently."""
        self.add_line("def format_csv_value(value, precision=None):")
        self.add_line('"""Format one value for CSV output."""', 1)
        self.add_line(
            "if precision is not None and isinstance(value, (int, float)) "
            "and not isinstance(value, bool):",
            1,
        )
        self.add_line('return f"{value:.{precision}f}"', 2)
        self.add_line("return str(value)", 1)

    def _emit_main_function(self, system: NncSystem):
        """Emit the generated CSV-oriented `main()` function."""
        input_vars = self._input_vars(system)
        output_vars = self._output_vars(system)

        self._emit_format_float_function()
        self.add_line()
        self.add_line()
        self.add_line("def main():")
        self.add_line('"""Main function for CSV processing."""', 1)
        self.add_line("import sys", 1)
        self.add_line("import csv", 1)
        self.add_line("import argparse", 1)
        self.add_line()

        self.add_line(
            "parser = argparse.ArgumentParser(description='TENNCell System Simulator')",
            1,
        )
        self.add_line(
            "parser.add_argument('--csv-include-initial', action='store_true', "
            "help='Write an initial state row before consuming CSV input')",
            1,
        )
        self.add_line(
            "parser.add_argument('--csv-no-initial', action='store_true', "
            "help='Suppress the initial state row for no-input systems')",
            1,
        )
        self.add_line(
            "parser.add_argument('--csv-delimiter', default=',', "
            "help='CSV delimiter used for input and output')",
            1,
        )
        self.add_line(
            "parser.add_argument('--csv-precision', type=int, default=None, "
            "help='Format numeric CSV output with this many decimal places')",
            1,
        )
        if input_vars:
            self.add_line("args = parser.parse_args()", 1)
        else:
            self.add_line(
                "parser.add_argument('steps', type=int, help='Number of steps to execute')",
                1,
            )
            self.add_line("args = parser.parse_args()", 1)
        self.add_line()

        self.add_line("system = NncSystem()", 1)
        self.add_line("if args.csv_delimiter == '':", 1)
        self.add_line(
            "print('Error: --csv-delimiter must be non-empty', file=sys.stderr)", 2
        )
        self.add_line("sys.exit(1)", 2)
        self.add_line(
            "if args.csv_precision is not None and args.csv_precision < 0:", 1
        )
        self.add_line(
            "print('Error: --csv-precision must be non-negative', file=sys.stderr)",
            2,
        )
        self.add_line("sys.exit(1)", 2)
        self.add_line()

        if input_vars:
            self.add_line("# Read CSV from stdin", 1)
            self.add_line(
                "reader = csv.DictReader(sys.stdin, delimiter=args.csv_delimiter)", 1
            )
            self.add_line("writer = None", 1)
            self.add_line()

            self.add_line("step_num = 0", 1)
            if output_vars:
                self.add_line("if args.csv_include_initial:", 1)
                self.add_line(f"fieldnames = ['step'] + {output_vars}", 2)
                self.add_line(
                    "writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames, "
                    "delimiter=args.csv_delimiter, lineterminator='\\n')",
                    2,
                )
                self.add_line("writer.writeheader()", 2)
                self.add_line("initial_output = {", 2)
                for var_name in output_vars:
                    self.add_line(
                        f"'{var_name}': format_csv_value(system.{var_name}, args.csv_precision),",
                        3,
                    )
                self.add_line("}", 2)
                self.add_line("step0_row = {'step': 0}", 2)
                self.add_line("step0_row.update(initial_output)", 2)
                self.add_line("writer.writerow(step0_row)", 2)
                self.add_line()
            self.add_line("# Process all input rows until exhausted", 1)
            self.add_line("while True:", 1)
            self.add_line("try:", 2)
            self.add_line("# Read next input row", 3)
            self.add_line("input_row = next(reader)", 3)

            self.add_line("# Convert input values to float", 3)
            self.add_line("inputs = {}", 3)
            for var_name in input_vars:
                self.add_line(f"if '{var_name}' in input_row:", 3)
                self.add_line(
                    f"inputs['{var_name}'] = float(input_row['{var_name}'])", 4
                )
                self.add_line(f"else:", 3)
                self.add_line(
                    f"print(f'Error: Input variable {var_name} not found in CSV row {{step_num + 1}}', file=sys.stderr)",
                    4,
                )
                self.add_line("sys.exit(1)", 4)
            self.add_line()

            self.add_line("# Execute step", 3)
            self.add_line("output = system.step(inputs)", 3)
            self.add_line()

            if output_vars:
                self.add_line("# Initialize CSV writer on first row", 3)
                self.add_line("if writer is None:", 3)
                self.add_line(f"fieldnames = ['step'] + {output_vars}", 4)
                self.add_line(
                    "writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames, "
                    "delimiter=args.csv_delimiter, lineterminator='\\n')",
                    4,
                )
                self.add_line("writer.writeheader()", 4)
                self.add_line()

                self.add_line(
                    "# Write output row with step number and formatted values", 3
                )
                self.add_line("output_row = {'step': step_num + 1}", 3)
                self.add_line(
                    "formatted_output = {k: format_csv_value(v, args.csv_precision) "
                    "for k, v in output.items()}",
                    3,
                )
                self.add_line("output_row.update(formatted_output)", 3)
                self.add_line("writer.writerow(output_row)", 3)

            self.add_line("step_num += 1", 3)

            self.add_line("except StopIteration:", 2)
            self.add_line("# No more input rows, processing complete", 3)
            self.add_line("if step_num == 0:", 3)
            self.add_line("print('Warning: No input data found.', file=sys.stderr)", 4)
            self.add_line("else:", 3)
            self.add_line(
                "print(f'Processed {step_num} input rows successfully.', file=sys.stderr)",
                4,
            )
            self.add_line("break", 3)
            self.add_line()
        else:
            self.add_line(
                "# No input variables - run steps and output CSV for each step", 1
            )
            self.add_line("writer = None", 1)
            self.add_line()

            if output_vars:
                self.add_line("# Initialize CSV writer", 1)
                self.add_line(f"fieldnames = ['step'] + {output_vars}", 1)
                self.add_line(
                    "writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames, "
                    "delimiter=args.csv_delimiter, lineterminator='\\n')",
                    1,
                )
                self.add_line("writer.writeheader()", 1)
                self.add_line()
                self.add_line("if not args.csv_no_initial:", 1)
                self.add_line("# Write initial state (step 0) with formatted values", 2)
                self.add_line("initial_output = {", 2)
                for var_name in output_vars:
                    self.add_line(
                        f"'{var_name}': format_csv_value(system.{var_name}, args.csv_precision),",
                        3,
                    )
                self.add_line("}", 2)
                self.add_line("step0_row = {'step': 0}", 2)
                self.add_line("step0_row.update(initial_output)", 2)
                self.add_line("writer.writerow(step0_row)", 2)
                self.add_line()
            else:
                self.add_line("# Initialize CSV writer with all variables", 1)
                self.add_line("all_vars = system.get_variables()", 1)
                self.add_line("fieldnames = ['step'] + list(all_vars.keys())", 1)
                self.add_line(
                    "writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames, "
                    "delimiter=args.csv_delimiter, lineterminator='\\n')",
                    1,
                )
                self.add_line("writer.writeheader()", 1)
                self.add_line()
                self.add_line("if not args.csv_no_initial:", 1)
                self.add_line("# Write initial state (step 0) with formatted values", 2)
                self.add_line("step0_row = {'step': 0}", 2)
                self.add_line(
                    "formatted_all_vars = {k: format_csv_value(v, args.csv_precision) "
                    "for k, v in all_vars.items()}",
                    2,
                )
                self.add_line("step0_row.update(formatted_all_vars)", 2)
                self.add_line("writer.writerow(step0_row)", 2)
                self.add_line()

            self.add_line("for step_num in range(args.steps):", 1)
            if output_vars:
                self.add_line("output = system.step()", 2)
                self.add_line(
                    "# Write output row with step number and formatted values", 2
                )
                self.add_line("output_row = {'step': step_num + 1}", 2)
                self.add_line(
                    "formatted_output = {k: format_csv_value(v, args.csv_precision) "
                    "for k, v in output.items()}",
                    2,
                )
                self.add_line("output_row.update(formatted_output)", 2)
                self.add_line("writer.writerow(output_row)", 2)
            else:
                self.add_line("system.step()", 2)
                self.add_line("all_vars = system.get_variables()", 2)
                self.add_line("# Write row with step number and formatted values", 2)
                self.add_line("all_vars_row = {'step': step_num + 1}", 2)
                self.add_line(
                    "formatted_all_vars = {k: format_csv_value(v, args.csv_precision) "
                    "for k, v in all_vars.items()}",
                    2,
                )
                self.add_line("all_vars_row.update(formatted_all_vars)", 2)
                self.add_line("writer.writerow(all_vars_row)", 2)

        self.add_line()
        self.add_line()
        self.add_line("if __name__ == '__main__':", 0)
        self.add_line("main()", 1)
