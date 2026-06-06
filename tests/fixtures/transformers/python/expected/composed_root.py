# Generated Python code from composed TENNCell system
import math

class _NncModuleBase:
    def _ref(self, reference):
        head, _, tail = reference.partition('.')
        module = getattr(self, f'_import_{head}', None)
        if module is None:
            raise ValueError(f'Unknown import reference {reference}')
        return getattr(module, tail)

    def _coerce_inputs(self, inputs, required_inputs):
        inputs = inputs or {}
        for var_name in required_inputs:
            if var_name not in inputs:
                raise ValueError(f'Input variable {var_name} is required but not provided')
        return inputs

class _Module_sensor(_NncModuleBase):
    def __init__(self):
        self.raw = 0.0
        self.level = 0.0

    def step(self, inputs=None):
        required_inputs = ['raw']
        inputs = self._coerce_inputs(inputs, required_inputs)
        # Update input variables
        self.raw = float(inputs['raw'])

        # TENNCell step using _new variables approach

        # Step 1: Initialize _new versions of all variables from current state
        level_new = self.level
        raw_new = self.raw

        # Step 2: Track variables consumed by active rules
        used_vars = set()

        # Step 3: Evaluate active rules and collect consumed variables
        # Rule 1
        level_new += (self.raw + 1.0)
        used_vars.add('raw')

        # Step 4: Remove old values from dynamically used variables
        if 'level' in used_vars:
            level_new -= self.level
        if 'raw' in used_vars:
            raw_new -= self.raw

        # Step 5: Update all variables to their final values
        self.level = level_new
        self.raw = raw_new

        # Return output variables
        return {
            'level': self.level,
        }

    def get_variables(self):
        return {
            'level': self.level,
            'raw': self.raw,
        }

class _Module_controller(_NncModuleBase):
    def __init__(self):
        self.sample = 0.0
        self.alarm = 0.0
        self._import_sensor0 = _Module_sensor()

    def step(self, inputs=None):
        required_inputs = ['sample']
        inputs = self._coerce_inputs(inputs, required_inputs)
        # Update input variables
        self.sample = float(inputs['sample'])

        self._import_sensor0.step({'raw': float(self.sample)})

        # TENNCell step using _new variables approach

        # Step 1: Initialize _new versions of all variables from current state
        alarm_new = self.alarm
        sample_new = self.sample

        # Step 2: Track variables consumed by active rules
        used_vars = set()

        # Step 3: Evaluate active rules and collect consumed variables
        # Rule 1
        if (self._ref('sensor0.level') > 2.0):
            alarm_new += self._ref('sensor0.level')

        # Step 4: Remove old values from dynamically used variables
        if 'alarm' in used_vars:
            alarm_new -= self.alarm
        if 'sample' in used_vars:
            sample_new -= self.sample

        # Step 5: Update all variables to their final values
        self.alarm = alarm_new
        self.sample = sample_new

        # Return output variables
        return {
            'alarm': self.alarm,
        }

    def get_variables(self):
        return {
            'alarm': self.alarm,
            'sample': self.sample,
        }

class NncSystem(_Module_controller):
    pass

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
            if 'sample' in input_row:
                inputs['sample'] = float(input_row['sample'])
            else:
                print(f'Error: Input variable sample not found in CSV row {step_num + 1}', file=sys.stderr)
                sys.exit(1)

            # Execute step
            output = system.step(inputs)

            # Initialize CSV writer on first row
            if writer is None:
                fieldnames = ['step'] + ['alarm']
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
