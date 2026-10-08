# Generated Python code from TENNCell system
import math

class NncSystem:
    def __init__(self):
        self.sensor = 0.0
        self.rounded = 0.1
        self.extreme = 1e+16
        self.motor = 0.1

    def step(self, inputs):
        """Execute one step of the TENNCell system.
        
        Args:
            inputs: Dictionary with input variable values (required)
        
        Returns:
            Dictionary with output variable values
        """
        # Validate that all input variables are provided
        required_inputs = ['sensor']
        for var_name in required_inputs:
            if var_name not in inputs:
                raise ValueError(f'Input variable {var_name} is required but not provided')

        # Update input variables
        self.sensor = inputs['sensor']

        # TENNCell step using _new variables approach

        # Step 1: Evaluate rules on the current state
        used_vars = set()
        # Rule 1
        _p0 = ((0.0 * self.rounded) + 0.05)
        used_vars.add('rounded')

        # Rule 2
        _p1 = 0.005

        # Rule 3
        _p2 = ((0.0 * self.extreme) + 1.0)
        used_vars.add('extreme')

        # Rule 4
        _p3 = ((0.0 * self.motor) + 0.05)
        used_vars.add('motor')

        # Rule 5
        _p4 = (0.005 * self.sensor)
        used_vars.add('sensor')

        # Step 2: Initialize _new versions of all variables from consumption state
        extreme_new = 0.0 if 'extreme' in used_vars else self.extreme
        motor_new = 0.0 if 'motor' in used_vars else self.motor
        rounded_new = 0.0 if 'rounded' in used_vars else self.rounded
        sensor_new = 0.0 if 'sensor' in used_vars else self.sensor

        # Step 3: Accumulate stored productions in rule order
        rounded_new += _p0
        rounded_new += _p1
        extreme_new += _p2
        motor_new += _p3
        motor_new += _p4

        # Step 4: Update all variables to their final values
        self.extreme = extreme_new
        self.motor = motor_new
        self.rounded = rounded_new
        self.sensor = sensor_new

        # Return output variables
        return {
            'rounded': self.rounded,
            'extreme': self.extreme,
            'motor': self.motor,
        }

    def get_variables(self):
        return {
            'extreme': self.extreme,
            'motor': self.motor,
            'rounded': self.rounded,
            'sensor': self.sensor,
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
        fieldnames = ['step'] + ['rounded', 'extreme', 'motor']
        writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames, delimiter=args.csv_delimiter, lineterminator='\n')
        writer.writeheader()
        initial_output = {
            'rounded': format_csv_value(system.rounded, args.csv_precision),
            'extreme': format_csv_value(system.extreme, args.csv_precision),
            'motor': format_csv_value(system.motor, args.csv_precision),
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
            if 'sensor' in input_row:
                inputs['sensor'] = float(input_row['sensor'])
            else:
                print(f'Error: Input variable sensor not found in CSV row {step_num + 1}', file=sys.stderr)
                sys.exit(1)

            # Execute step
            output = system.step(inputs)

            # Initialize CSV writer on first row
            if writer is None:
                fieldnames = ['step'] + ['rounded', 'extreme', 'motor']
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
