# Generated Python code from TENNCell system
import math

class NncSystem:
    def __init__(self):
        self.x = 0.0
        self.out = 0.0

    def step(self):
        """Execute one step of the TENNCell system.
        
        Returns:
            Dictionary with output variable values
        """
        # TENNCell step using _new variables approach

        # Step 1: Evaluate rules on the current state
        used_vars = set()
        # Rule 1
        _p0 = (self.x + 1.0)
        used_vars.add('x')

        # Step 2: Initialize _new versions of all variables from consumption state
        out_new = 0.0 if 'out' in used_vars else self.out
        x_new = 0.0 if 'x' in used_vars else self.x

        # Step 3: Accumulate stored productions in rule order
        out_new += _p0

        # Step 4: Update all variables to their final values
        self.out = out_new
        self.x = x_new

        # Return output variables
        return {
            'out': self.out,
        }

    def get_variables(self):
        return {
            'out': self.out,
            'x': self.x,
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
    parser.add_argument('steps', type=int, help='Number of steps to execute')
    args = parser.parse_args()

    system = NncSystem()
    if args.csv_delimiter == '':
        print('Error: --csv-delimiter must be non-empty', file=sys.stderr)
        sys.exit(1)
    if args.csv_precision is not None and args.csv_precision < 0:
        print('Error: --csv-precision must be non-negative', file=sys.stderr)
        sys.exit(1)

    # No input variables - run steps and output CSV for each step
    writer = None

    # Initialize CSV writer
    fieldnames = ['step'] + ['out']
    writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames, delimiter=args.csv_delimiter, lineterminator='\n')
    writer.writeheader()

    if not args.csv_no_initial:
        # Write initial state (step 0) with formatted values
        initial_output = {
            'out': format_csv_value(system.out, args.csv_precision),
        }
        step0_row = {'step': 0}
        step0_row.update(initial_output)
        writer.writerow(step0_row)

    for step_num in range(args.steps):
        output = system.step()
        # Write output row with step number and formatted values
        output_row = {'step': step_num + 1}
        formatted_output = {k: format_csv_value(v, args.csv_precision) for k, v in output.items()}
        output_row.update(formatted_output)
        writer.writerow(output_row)


if __name__ == '__main__':
    main()
