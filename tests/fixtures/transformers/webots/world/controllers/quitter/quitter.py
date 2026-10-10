"""Supervisor of the Webots runtime fixture: quit after a few steps."""

from controller import Supervisor

STEPS = 5

supervisor = Supervisor()
count = 0
while supervisor.step(32) != -1:
    count += 1
    if count == STEPS:
        supervisor.simulationQuit(0)
