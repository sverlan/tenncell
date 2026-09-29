"""Generated Webots controller from TENNCell system."""
import csv
from controller import Robot

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
    csv_writer = csv.writer(csv_file)
    csv_writer.writerow(['_step', '_time', 'input_x', 'out'])
    step_index = 0

    while robot.step(timestep) != -1:
        inputs = {
            'input_x': float(devices['input_x'].getValue()),
        }
        nnc.step(inputs)
        variables = nnc.get_variables()
        csv_writer.writerow([step_index, robot.getTime(), variables['input_x'], variables['out']])
        csv_file.flush()
        step_index += 1
        devices['out'].setValue(variables['out'])

if __name__ == '__main__':
    main()
