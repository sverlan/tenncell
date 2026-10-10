# Pasted at the top level of the generated controller (webots.code.module).

# e-puck wheel speed limit (rad/s).
MAX_SPEED = 6.28


class Combined:
    """Virtual device: several real sensors read as one value.

    `reduce` combines their readings: `max` for e-puck proximity sensors,
    whose values grow as an obstacle comes closer (so `max` is the closest
    obstacle on that side), `min` for sensors that report a distance.
    """

    def __init__(self, robot, names, timestep, reduce=max):
        self.sensors = [robot.getDevice(name) for name in names]
        for sensor in self.sensors:
            sensor.enable(timestep)
        self.reduce = reduce

    def getValue(self):
        return self.reduce(sensor.getValue() for sensor in self.sensors)


def add_clamped_velocity(motor):
    """Give a real motor a `set_speed` method that keeps the model's speed
    within the e-puck's limits (Webots warns and clamps otherwise)."""

    def set_speed(value):
        motor.setVelocity(max(-MAX_SPEED, min(MAX_SPEED, value)))

    motor.set_speed = set_speed
