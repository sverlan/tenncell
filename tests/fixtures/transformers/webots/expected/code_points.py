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

        # Step 2: Initialize _new versions of all variables from consumption state
        distance_new = 0.0 if 'distance' in used_vars else self.distance
        speed_new = 0.0 if 'speed' in used_vars else self.speed

        # Step 3: Accumulate stored productions in rule order
        speed_new += _p0
        speed_new += _p1

        # Step 4: Update all variables to their final values
        self.distance = distance_new
        self.speed = speed_new

        # Return output variables
        return {
            'speed': self.speed,
        }

    def get_variables(self):
        return {
            'distance': self.distance,
            'speed': self.speed,
        }

# Webots controller: code_points

# webots code: module (code/module.py)
def mark(*words):
    """Print a marker line (the simulator records printed lines in order)."""
    print(*words)


def scaled(value):
    return value * 0.001
# end webots code: module

def main():
    robot = Robot()
    timestep = 32
    nnc = NncSystem()

    devices = {
        'distance': robot.getDevice('distance_sensor'),
        'speed': robot.getDevice('wheel'),
    }
    # webots code: setup (inline)
    mark("setup", timestep)
    # end webots code: setup

    if hasattr(devices['distance'], 'enable'):
        devices['distance'].enable(timestep)

    csv_file = open('code_points.csv', 'w', newline='')
    csv_writer = csv.writer(csv_file, delimiter=',')
    csv_writer.writerow(['speed'])
    step_index = 0

    try:
        while robot.step(timestep) != -1:
            inputs = {
                'distance': float(devices['distance'].getValue()),
            }
            # webots code: before_step (inline)
            mark("before_step", inputs["distance"])
            inputs["distance"] = scaled(inputs["distance"])
            # end webots code: before_step
            nnc.step(inputs)
            variables = nnc.get_variables()
            step_index += 1
            csv_writer.writerow([format_csv_value(variables['speed'], None)])
            csv_file.flush()
            # webots code: after_step (code/after_step.py)
            mark("after_step", variables["speed"])

            if variables["speed"] > 1:
                mark("fast")
            # end webots code: after_step
            devices['speed'].setVelocity(variables['speed'])
    finally:
        csv_file.close()
        # webots code: shutdown (inline)
        mark('shutdown')
        # end webots code: shutdown

if __name__ == '__main__':
    main()
