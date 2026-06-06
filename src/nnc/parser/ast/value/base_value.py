from abc import ABC
from typing import Any


class Value(ABC):
    """
    A class to represent a value.

    Attributes
    ----------
    type : str
        a string representing the type of the Value
    value :
        The value of the Value

    Methods
    -------
    __init__(type, value):
        Constructs a Value instance from a float, int, or str.
    __str__():
        Returns a string representation of the value.
    __repr__():
    """

    value: Any

    def __init__(self, value: Any):
        """Initializes the Value with a given type."""
        self.value = value
        # self.type = value_type


class SimpleValue(Value, ABC):
    pass
