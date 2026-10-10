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
        self.distance = 0.0
        self.speed = 0.0
        self.position = 0.0
        self.led_on = 0.0

    def step(self, inputs):
        """Execute one step of the TENNCell system.

        Args:
            inputs: Dictionary with input variable values (required)

        Returns:
            Dictionary with output variable values
        """
        # Validate that all input variables are provided
        required_inputs = ['distance']
        for var_name in required_inputs:
            if var_name not in inputs:
                raise ValueError(f'Input variable {var_name} is required but not provided')

        # Update input variables
        self.distance = inputs['distance']

        # TENNCell step using _new variables approach

        # Step 1: Evaluate rules on the current state
        used_vars = set()
        # Rule 1
        _p0 = self.distance
        used_vars.add('distance')

        # Rule 2
        _p1 = (self.speed * 0.0)
        used_vars.add('speed')

        # Rule 3
        _p2 = 1.0

        # Rule 4
        _p3 = (self.led_on * 0.0)
        used_vars.add('led_on')

        # Step 2: Initialize _new versions of all variables from consumption state
        distance_new = 0.0 if 'distance' in used_vars else self.distance
        led_on_new = 0.0 if 'led_on' in used_vars else self.led_on
        position_new = 0.0 if 'position' in used_vars else self.position
        speed_new = 0.0 if 'speed' in used_vars else self.speed

        # Step 3: Accumulate stored productions in rule order
        speed_new += _p0
        speed_new += _p1
        led_on_new += _p2
        led_on_new += _p3

        # Step 4: Update all variables to their final values
        self.distance = distance_new
        self.led_on = led_on_new
        self.position = position_new
        self.speed = speed_new

        # Return output variables
        return {
            'speed': self.speed,
            'led_on': self.led_on,
        }

    def get_variables(self):
        return {
            'distance': self.distance,
            'led_on': self.led_on,
            'position': self.position,
            'speed': self.speed,
        }

# Webots controller: code_patch

def main():
    robot = Robot()
    timestep = 32
    nnc = NncSystem()

    devices = {
        'distance': robot.getDevice('distance_sensor'),
        'speed': robot.getDevice('wheel'),
        'position': robot.getDevice('wheel'),
        'led_on': robot.getDevice('led'),
    }
    # webots code: setup (inline)
    sensor, wheel, led = devices['distance'], devices['speed'], devices['led_on']
    sensor.read_scaled = lambda: sensor.getValue() * 0.001
    wheel.park = lambda value: wheel.setPosition(value)
    led.set_int = lambda value: led.set(int(value))
    # end webots code: setup

    if hasattr(devices['distance'], 'enable'):
        devices['distance'].enable(timestep)

    devices['position'].park(float('inf'))

    csv_file = open('code_patch.csv', 'w', newline='')
    csv_writer = csv.writer(csv_file, delimiter=',')
    csv_writer.writerow(['speed', 'led_on'])
    step_index = 0

    try:
        while robot.step(timestep) != -1:
            inputs = {
                'distance': float(devices['distance'].read_scaled()),
            }
            nnc.step(inputs)
            variables = nnc.get_variables()
            step_index += 1
            csv_writer.writerow([format_csv_value(variables['speed'], None), format_csv_value(variables['led_on'], None)])
            csv_file.flush()
            devices['speed'].setVelocity(variables['speed'])
            devices['led_on'].set_int(variables['led_on'])
    finally:
        csv_file.close()

if __name__ == '__main__':
    main()
