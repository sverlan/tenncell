from typing import Any

from .base_value import Value


class ArrayValue(Value):
    """ "
    A class to represent an array value.

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
        Returns a string representation of the value.
    __getitem__(key):
        Returns the value at the given index.
    """

    base_type: Any
    value: list[Value]

    def __init__(self, base_type: Any, array_value):
        super().__init__(array_value)
        self.base_type = base_type

    def __str__(self):
        return f"[{','.join([str(v) for v in self.value])}]"  # pragma: no cover

    def __repr__(self):
        return f"ArrayValue({str(self.base_type)},{self.value})"

    def __getitem__(self, key):
        return self.value[key]

    def __setitem__(self, key, value):
        self.value[key] = value

    def append(self, value):
        self.value.append(value)

    def __len__(self):
        return len(self.value)

    def __iter__(self):
        return iter(self.value)

    def __contains__(self, item):
        return item in self.value

    def __eq__(self, other):
        if isinstance(other, ArrayValue):
            return self.value == other.value
        else:
            return False
