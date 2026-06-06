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

        # Step 1: Initialize _new versions of all variables from current state
        out_new = self.out
        x_new = self.x

        # Step 2: Track variables consumed by active rules
        used_vars = set()

        # Step 3: Evaluate active rules and collect consumed variables
        # Rule 1
        out_new += (self.x + 1.0)
        used_vars.add('x')

        # Step 4: Remove old values from dynamically used variables
        if 'out' in used_vars:
            out_new -= self.out
        if 'x' in used_vars:
            x_new -= self.x

        # Step 5: Update all variables to their final values
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
    parser.add_argument('steps', type=int, help='Number of steps to execute')
    args = parser.parse_args()

    system = NncSystem()

    # No input variables - run steps and output CSV for each step
    writer = None

    # Initialize CSV writer
    fieldnames = ['step'] + ['out']
    writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames, lineterminator='\n')
    writer.writeheader()

    # Write initial state (step 0) with formatted values
    initial_output = {
        'out': format_float(system.out),
    }
    step0_row = {'step': 0}
    step0_row.update(initial_output)
    writer.writerow(step0_row)

    for step_num in range(args.steps):
        output = system.step()
        # Write output row with step number and formatted values
        output_row = {'step': step_num + 1}
        formatted_output = {k: format_float(v) for k, v in output.items()}
        output_row.update(formatted_output)
        writer.writerow(output_row)


if __name__ == '__main__':
    main()
