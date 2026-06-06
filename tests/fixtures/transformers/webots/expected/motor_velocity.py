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

        # Step 1: Initialize _new versions of all variables from current state
        left_position_new = self.left_position
        left_speed_new = self.left_speed
        right_position_new = self.right_position
        right_speed_new = self.right_speed

        # Step 2: Track variables consumed by active rules
        used_vars = set()

        # Step 3: Evaluate active rules and collect consumed variables
        # Rule 1
        left_speed_new += 1.0

        # Rule 2
        right_speed_new += 2.0

        # Step 4: Remove old values from dynamically used variables
        if 'left_position' in used_vars:
            left_position_new -= self.left_position
        if 'left_speed' in used_vars:
            left_speed_new -= self.left_speed
        if 'right_position' in used_vars:
            right_position_new -= self.right_position
        if 'right_speed' in used_vars:
            right_speed_new -= self.right_speed

        # Step 5: Update all variables to their final values
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
