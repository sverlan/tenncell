"""Generated Webots controller from TENNCell system."""
from controller import Robot

# Generated Python code from TENNCell system
import math

class NncSystem:
    def __init__(self):
        self.nearest = 0.0
        self.echo = 0.0

    def step(self, inputs):
        """Execute one step of the TENNCell system.

        Args:
            inputs: Dictionary with input variable values (required)

        Returns:
            Dictionary with output variable values
        """
        # Validate that all input variables are provided
        required_inputs = ['nearest']
        for var_name in required_inputs:
            if var_name not in inputs:
                raise ValueError(f'Input variable {var_name} is required but not provided')

        # Update input variables
        self.nearest = inputs['nearest']

        # TENNCell step using _new variables approach

        # Step 1: Evaluate rules on the current state
        used_vars = set()
        # Rule 1
        _p0 = self.nearest
        used_vars.add('nearest')

        # Rule 2
        _p1 = (self.echo * 0.0)
        used_vars.add('echo')

        # Step 2: Initialize _new versions of all variables from consumption state
        echo_new = 0.0 if 'echo' in used_vars else self.echo
        nearest_new = 0.0 if 'nearest' in used_vars else self.nearest

        # Step 3: Accumulate stored productions in rule order
        echo_new += _p0
        echo_new += _p1

        # Step 4: Update all variables to their final values
        self.echo = echo_new
        self.nearest = nearest_new

        # Return output variables
        return {
            'echo': self.echo,
        }

    def get_variables(self):
        return {
            'echo': self.echo,
            'nearest': self.nearest,
        }

# Webots controller: code_virtual

# webots code: module (inline)
class Nearest:
    def __init__(self, sensor):
        self.sensor = sensor

    def read(self):
        return self.sensor.getValue() * 0.001


class Recorder:
    def __init__(self, path):
        self.file = open(path, "w")

    def record(self, value):
        self.file.write(f"{value}\n")
        self.file.flush()
# end webots code: module

def main():
    robot = Robot()
    timestep = 32
    nnc = NncSystem()

    devices = {
        'nearest': None,  # virtual: set by setup code
        'echo': None,  # virtual: set by setup code
    }
    # webots code: setup (inline)
    sensor = robot.getDevice("distance_sensor")
    sensor.enable(timestep)
    devices["nearest"] = Nearest(sensor)
    devices["echo"] = Recorder("echo.txt")
    # end webots code: setup

    if devices['nearest'] is None:
        raise RuntimeError("Webots binding 'nearest' has no device: webots.code.setup must set devices['nearest']")
    if devices['echo'] is None:
        raise RuntimeError("Webots binding 'echo' has no device: webots.code.setup must set devices['echo']")

    if hasattr(devices['nearest'], 'enable'):
        devices['nearest'].enable(timestep)

    devices['echo'].record(-1)

    while robot.step(timestep) != -1:
        inputs = {
            'nearest': float(devices['nearest'].read()),
        }
        nnc.step(inputs)
        variables = nnc.get_variables()
        devices['echo'].record(variables['echo'])

if __name__ == '__main__':
    main()
