"""Generated Webots controller from TENNCell system."""
import csv
from controller import Robot

def format_csv_value(value, precision=None):
    """Format one value for CSV output."""
    if precision is not None and isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{value:.{precision}f}"
    return str(value)

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

# Webots controller: sensor_led_controller

def main():
    robot = Robot()
    timestep = 32
    nnc = NncSystem()

    devices = {
        'input_x': robot.getDevice('distance_sensor'),
        'out': robot.getDevice('led'),
    }
    if hasattr(devices['input_x'], 'enable'):
        devices['input_x'].enable(timestep)

    csv_file = open('sensor_led.csv', 'w', newline='')
    csv_writer = csv.writer(csv_file, delimiter=',')
    csv_writer.writerow(['_step', '_time', 'input_x', 'out'])
    step_index = 0
    variables = nnc.get_variables()
    csv_writer.writerow([step_index, format_csv_value(robot.getTime(), None), format_csv_value(variables['input_x'], None), format_csv_value(variables['out'], None)])
    csv_file.flush()

    while robot.step(timestep) != -1:
        inputs = {
            'input_x': float(devices['input_x'].getValue()),
        }
        nnc.step(inputs)
        variables = nnc.get_variables()
        step_index += 1
        csv_writer.writerow([step_index, format_csv_value(robot.getTime(), None), format_csv_value(variables['input_x'], None), format_csv_value(variables['out'], None)])
        csv_file.flush()
        devices['out'].setValue(variables['out'])

if __name__ == '__main__':
    main()
