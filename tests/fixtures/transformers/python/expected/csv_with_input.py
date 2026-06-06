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

        # Step 1: Initialize _new versions of all variables from current state
        input_x_new = self.input_x
        out_new = self.out

        # Step 2: Track variables consumed by active rules
        used_vars = set()

        # Step 3: Evaluate active rules and collect consumed variables
        # Rule 1
        out_new += (self.input_x + 1.0)
        used_vars.add('input_x')

        # Step 4: Remove old values from dynamically used variables
        if 'input_x' in used_vars:
            input_x_new -= self.input_x
        if 'out' in used_vars:
            out_new -= self.out

        # Step 5: Update all variables to their final values
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


def format_float(value):
    """Format float values with proper precision."""
    if isinstance(value, (int, float)):
        return f"{value:.6f}".rstrip("0").rstrip(".")
    return str(value)


def main():
    """Main function for CSV processing."""
    import sys
    import csv
    import argparse

    parser = argparse.ArgumentParser(description='TENNCell System Simulator')
    args = parser.parse_args()

    system = NncSystem()

    # Read CSV from stdin
    reader = csv.DictReader(sys.stdin)
    writer = None

    step_num = 0
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
                writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames, lineterminator='\n')
                writer.writeheader()

            # Write output row with step number and formatted values
            output_row = {'step': step_num + 1}
            formatted_output = {k: format_float(v) for k, v in output.items()}
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
