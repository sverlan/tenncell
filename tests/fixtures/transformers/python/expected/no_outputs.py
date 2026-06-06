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

        # Step 1: Initialize _new versions of all variables from current state
        x_new = self.x

        # Step 2: Track variables consumed by active rules
        used_vars = set()

        # Step 3: Evaluate active rules and collect consumed variables
        # Step 4: Remove old values from dynamically used variables
        if 'x' in used_vars:
            x_new -= self.x

        # Step 5: Update all variables to their final values
        self.x = x_new

        # No output variables defined, return all variables
        return self.get_variables()

    def get_variables(self):
        return {
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

    # Initialize CSV writer with all variables
    all_vars = system.get_variables()
    fieldnames = ['step'] + list(all_vars.keys())
    writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames, lineterminator='\n')
    writer.writeheader()

    # Write initial state (step 0) with formatted values
    step0_row = {'step': 0}
    formatted_all_vars = {k: format_float(v) for k, v in all_vars.items()}
    step0_row.update(formatted_all_vars)
    writer.writerow(step0_row)

    for step_num in range(args.steps):
        system.step()
        all_vars = system.get_variables()
        # Write row with step number and formatted values
        all_vars_row = {'step': step_num + 1}
        formatted_all_vars = {k: format_float(v) for k, v in all_vars.items()}
        all_vars_row.update(formatted_all_vars)
        writer.writerow(all_vars_row)


if __name__ == '__main__':
    main()
