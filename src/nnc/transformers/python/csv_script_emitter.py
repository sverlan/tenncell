"""CSV command-line script emission for generated Python TENNCell systems."""

from ...model.system import NncSystem


class PythonCsvScriptEmitter:
    """Emit the CSV executable wrapper around generated Python TENNCell systems."""

    def _emit_format_float_function(self):
        """Emit a helper that formats numeric CSV output consistently."""
        self.add_line("def format_float(value):")
        self.add_line('"""Format float values with proper precision."""', 1)
        self.add_line("if isinstance(value, (int, float)):", 1)
        self.add_line('return f"{value:.6f}".rstrip("0").rstrip(".")', 2)
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
            "parser = argparse.ArgumentParser(description='TENNCell System Simulator')", 1
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
        self.add_line()

        if input_vars:
            self.add_line("# Read CSV from stdin", 1)
            self.add_line("reader = csv.DictReader(sys.stdin)", 1)
            self.add_line("writer = None", 1)
            self.add_line()

            self.add_line("step_num = 0", 1)
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
                    "writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames, lineterminator='\\n')",
                    4,
                )
                self.add_line("writer.writeheader()", 4)
                self.add_line()

                self.add_line(
                    "# Write output row with step number and formatted values", 3
                )
                self.add_line("output_row = {'step': step_num + 1}", 3)
                self.add_line(
                    "formatted_output = {k: format_float(v) for k, v in output.items()}",
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
                    "writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames, lineterminator='\\n')",
                    1,
                )
                self.add_line("writer.writeheader()", 1)
                self.add_line()
                self.add_line("# Write initial state (step 0) with formatted values", 1)
                self.add_line("initial_output = {", 1)
                for var_name in output_vars:
                    self.add_line(f"'{var_name}': format_float(system.{var_name}),", 2)
                self.add_line("}", 1)
                self.add_line("step0_row = {'step': 0}", 1)
                self.add_line("step0_row.update(initial_output)", 1)
                self.add_line("writer.writerow(step0_row)", 1)
                self.add_line()
            else:
                self.add_line("# Initialize CSV writer with all variables", 1)
                self.add_line("all_vars = system.get_variables()", 1)
                self.add_line("fieldnames = ['step'] + list(all_vars.keys())", 1)
                self.add_line(
                    "writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames, lineterminator='\\n')",
                    1,
                )
                self.add_line("writer.writeheader()", 1)
                self.add_line()
                self.add_line("# Write initial state (step 0) with formatted values", 1)
                self.add_line("step0_row = {'step': 0}", 1)
                self.add_line(
                    "formatted_all_vars = {k: format_float(v) for k, v in all_vars.items()}",
                    1,
                )
                self.add_line("step0_row.update(formatted_all_vars)", 1)
                self.add_line("writer.writerow(step0_row)", 1)
                self.add_line()

            self.add_line("for step_num in range(args.steps):", 1)
            if output_vars:
                self.add_line("output = system.step()", 2)
                self.add_line(
                    "# Write output row with step number and formatted values", 2
                )
                self.add_line("output_row = {'step': step_num + 1}", 2)
                self.add_line(
                    "formatted_output = {k: format_float(v) for k, v in output.items()}",
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
                    "formatted_all_vars = {k: format_float(v) for k, v in all_vars.items()}",
                    2,
                )
                self.add_line("all_vars_row.update(formatted_all_vars)", 2)
                self.add_line("writer.writerow(all_vars_row)", 2)

        self.add_line()
        self.add_line()
        self.add_line("if __name__ == '__main__':", 0)
        self.add_line("main()", 1)
