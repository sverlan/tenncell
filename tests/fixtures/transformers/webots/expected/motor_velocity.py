"""Generated Webots controller from TENNCell system."""
from controller import Robot

# Generated Python code from TENNCell system
import math

class NncSystem:
    def __init__(self):
        self.left_speed = 0.0
        self.right_speed = 0.0
        self.left_position = 0.0
        self.right_position = 0.0

    def step(self):
        """Execute one step of the TENNCell system.

        Returns:
            Dictionary with output variable values
        """
        # TENNCell step using _new variables approach

        # Step 1: Evaluate rules on the current state
        used_vars = set()
        # Rule 1
        _p0 = 1.0

        # Rule 2
        _p1 = 2.0

        # Step 2: Initialize _new versions of all variables from consumption state
        left_position_new = 0.0 if 'left_position' in used_vars else self.left_position
        left_speed_new = 0.0 if 'left_speed' in used_vars else self.left_speed
        right_position_new = 0.0 if 'right_position' in used_vars else self.right_position
        right_speed_new = 0.0 if 'right_speed' in used_vars else self.right_speed

        # Step 3: Accumulate stored productions in rule order
        left_speed_new += _p0
        right_speed_new += _p1

        # Step 4: Update all variables to their final values
        self.left_position = left_position_new
        self.left_speed = left_speed_new
        self.right_position = right_position_new
        self.right_speed = right_speed_new

        # Return output variables
        return {
            'left_speed': self.left_speed,
            'right_speed': self.right_speed,
        }

    def get_variables(self):
        return {
            'left_position': self.left_position,
            'left_speed': self.left_speed,
            'right_position': self.right_position,
            'right_speed': self.right_speed,
        }

# Webots controller: motor_velocity_controller

def main():
    robot = Robot()
    timestep = 64
    nnc = NncSystem()

    devices = {
        'left_speed': robot.getDevice('left wheel'),
        'right_speed': robot.getDevice('right wheel'),
        'left_position': robot.getDevice('left wheel'),
        'right_position': robot.getDevice('right wheel'),
    }
    devices['left_position'].setPosition(float('inf'))
    devices['right_position'].setPosition(float('inf'))

    while robot.step(timestep) != -1:
        nnc.step()
        variables = nnc.get_variables()
        devices['left_speed'].setVelocity(variables['left_speed'])
        devices['right_speed'].setVelocity(variables['right_speed'])

if __name__ == '__main__':
    main()
