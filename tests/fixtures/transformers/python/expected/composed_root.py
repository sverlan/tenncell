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

        # Step 1: Evaluate rules on the current state
        used_vars = set()
        # Rule 1
        _p0 = (self.raw + 1.0)
        used_vars.add('raw')

        # Step 2: Initialize _new versions of all variables from consumption state
        level_new = 0.0 if 'level' in used_vars else self.level
        raw_new = 0.0 if 'raw' in used_vars else self.raw

        # Step 3: Accumulate stored productions in rule order
        level_new += _p0

        # Step 4: Update all variables to their final values
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

        # Step 1: Evaluate rules on the current state
        used_vars = set()
        # Rule 1
        _g0 = (self._ref('sensor0.level') > 2.0)
        if _g0:
            _p0 = self._ref('sensor0.level')

        # Step 2: Initialize _new versions of all variables from consumption state
        alarm_new = 0.0 if 'alarm' in used_vars else self.alarm
        sample_new = 0.0 if 'sample' in used_vars else self.sample

        # Step 3: Accumulate stored productions in rule order
        if _g0:
            alarm_new += _p0

        # Step 4: Update all variables to their final values
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
        fieldnames = ['step'] + ['alarm']
        writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames, delimiter=args.csv_delimiter, lineterminator='\n')
        writer.writeheader()
        initial_output = {
            'alarm': format_csv_value(system.alarm, args.csv_precision),
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
