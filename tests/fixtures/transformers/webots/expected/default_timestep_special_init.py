"""Generated Webots controller from TENNCell system."""
from controller import Robot

# Generated Python code from TENNCell system
import math

class NncSystem:
    def __init__(self):
        self.tick = 0.0
        self.left_position = 0.0
        self.right_position = 0.0

    def step(self):
        """Execute one step of the TENNCell system.

        Returns:
            Dictionary with all variable values
        """
        # TENNCell step using _new variables approach

        # Step 1: Evaluate rules on the current state
        used_vars = set()
        # Rule 1
        _p0 = (self.tick + 1.0)
        used_vars.add('tick')

        # Step 2: Initialize _new versions of all variables from consumption state
        left_position_new = 0.0 if 'left_position' in used_vars else self.left_position
        right_position_new = 0.0 if 'right_position' in used_vars else self.right_position
        tick_new = 0.0 if 'tick' in used_vars else self.tick

        # Step 3: Accumulate stored productions in rule order
        tick_new += _p0

        # Step 4: Update all variables to their final values
        self.left_position = left_position_new
        self.right_position = right_position_new
        self.tick = tick_new

        # No output variables defined, return all variables
        return self.get_variables()

    def get_variables(self):
        return {
            'left_position': self.left_position,
            'right_position': self.right_position,
            'tick': self.tick,
        }

# Webots controller: default_timestep_special_init

def main():
    robot = Robot()
    timestep = int(robot.getBasicTimeStep())
    nnc = NncSystem()

    devices = {
        'left_position': robot.getDevice('left wheel'),
        'right_position': robot.getDevice('right wheel'),
    }
    devices['left_position'].setPosition(float('-inf'))
    devices['right_position'].setPosition(float('nan'))

    while robot.step(timestep) != -1:
        nnc.step()
        variables = nnc.get_variables()
        pass

if __name__ == '__main__':
    main()
