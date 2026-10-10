# Generated Python code from TENNCell system
import math

class NncSystem:
    def __init__(self):
        self.input_x = 0.0
        self.out = 0.0

    def step(self, inputs):
        """Execute one step of the TENNCell system.

        Args:
            inputs: Dictionary with input variable values (required)

        Returns:
            Dictionary with output variable values
        """
        # Validate that all input variables are provided
        required_inputs = ['input_x']
        for var_name in required_inputs:
            if var_name not in inputs:
                raise ValueError(f'Input variable {var_name} is required but not provided')

        # Update input variables
        self.input_x = inputs['input_x']

        # TENNCell step using _new variables approach

        # Step 1: Evaluate rules on the current state
        used_vars = set()
        # Rule 1
        _p0 = (self.input_x + 1.0)
        used_vars.add('input_x')

        # Step 2: Initialize _new versions of all variables from consumption state
        input_x_new = 0.0 if 'input_x' in used_vars else self.input_x
        out_new = 0.0 if 'out' in used_vars else self.out

        # Step 3: Accumulate stored productions in rule order
        out_new += _p0

        # Step 4: Update all variables to their final values
        self.input_x = input_x_new
        self.out = out_new

        # Return output variables
        return {
            'out': self.out,
        }

    def get_variables(self):
        return {
            'input_x': self.input_x,
            'out': self.out,
        }


def format_csv_value(value, precision=None):
    """Format one value for CSV output."""
    if precision is not None and isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{value:.{precision}f}"
    return str(value)


def main():
    """Main function for CSV processing."""
    import sys
    import csv
    import argparse

    parser = argparse.ArgumentParser(description='TENNCell System Simulator')
    parser.add_argument('--csv-include-initial', action='store_true', help='Write an initial state row before consuming CSV input')
    parser.add_argument('--csv-no-initial', action='store_true', help='Suppress the initial state row for no-input systems')
    parser.add_argument('--csv-delimiter', default=',', help='CSV delimiter used for input and output')
    parser.add_argument('--csv-precision', type=int, default=None, help='Format numeric CSV output with this many decimal places')
    args = parser.parse_args()

    system = NncSystem()
    if args.csv_delimiter == '':
        print('Error: --csv-delimiter must be non-empty', file=sys.stderr)
        sys.exit(1)
    if args.csv_precision is not None and args.csv_precision < 0:
        print('Error: --csv-precision must be non-negative', file=sys.stderr)
        sys.exit(1)

    # Read CSV from stdin
    reader = csv.DictReader(sys.stdin, delimiter=args.csv_delimiter)
    writer = None

    step_num = 0
    if args.csv_include_initial:
        fieldnames = ['step'] + ['out']
        writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames, delimiter=args.csv_delimiter, lineterminator='\n')
        writer.writeheader()
        initial_output = {
            'out': format_csv_value(system.out, args.csv_precision),
        }
        step0_row = {'step': 0}
        step0_row.update(initial_output)
        writer.writerow(step0_row)

    # Process all input rows until exhausted
    while True:
        try:
            # Read next input row
            input_row = next(reader)
            # Convert input values to float
            inputs = {}
            if 'input_x' in input_row:
                inputs['input_x'] = float(input_row['input_x'])
            else:
                print(f'Error: Input variable input_x not found in CSV row {step_num + 1}', file=sys.stderr)
                sys.exit(1)

            # Execute step
            output = system.step(inputs)

            # Initialize CSV writer on first row
            if writer is None:
                fieldnames = ['step'] + ['out']
                writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames, delimiter=args.csv_delimiter, lineterminator='\n')
                writer.writeheader()

            # Write output row with step number and formatted values
            output_row = {'step': step_num + 1}
            formatted_output = {k: format_csv_value(v, args.csv_precision) for k, v in output.items()}
            output_row.update(formatted_output)
            writer.writerow(output_row)
            step_num += 1
        except StopIteration:
            # No more input rows, processing complete
            if step_num == 0:
                print('Warning: No input data found.', file=sys.stderr)
            else:
                print(f'Processed {step_num} input rows successfully.', file=sys.stderr)
            break



if __name__ == '__main__':
    main()
