# Generated Python code from TENNCell system
import math

class NncSystem:
    def __init__(self):
        self.x = 0.0

    def step(self):
        """Execute one step of the TENNCell system.

        Returns:
            Dictionary with all variable values
        """
        # TENNCell step using _new variables approach

        # Step 1: Evaluate rules on the current state
        used_vars = set()
        # Step 2: Initialize _new versions of all variables from consumption state
        x_new = 0.0 if 'x' in used_vars else self.x

        # Step 3: Accumulate stored productions in rule order

        # Step 4: Update all variables to their final values
        self.x = x_new

        # No output variables defined, return all variables
        return self.get_variables()

    def get_variables(self):
        return {
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

    # Initialize CSV writer with all variables
    all_vars = system.get_variables()
    fieldnames = ['step'] + list(all_vars.keys())
    writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames, delimiter=args.csv_delimiter, lineterminator='\n')
    writer.writeheader()

    if not args.csv_no_initial:
        # Write initial state (step 0) with formatted values
        step0_row = {'step': 0}
        formatted_all_vars = {k: format_csv_value(v, args.csv_precision) for k, v in all_vars.items()}
        step0_row.update(formatted_all_vars)
        writer.writerow(step0_row)

    for step_num in range(args.steps):
        system.step()
        all_vars = system.get_variables()
        # Write row with step number and formatted values
        all_vars_row = {'step': step_num + 1}
        formatted_all_vars = {k: format_csv_value(v, args.csv_precision) for k, v in all_vars.items()}
        all_vars_row.update(formatted_all_vars)
        writer.writerow(all_vars_row)


if __name__ == '__main__':
    main()
