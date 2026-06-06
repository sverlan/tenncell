from __future__ import annotations

from .numerical_value import NumericalValue


class FloatValue(NumericalValue):
    def __init__(self, value: float | int | str = 0.0):
        """Initialize the numerical value from a float, int, or string."""
        if isinstance(value, float):
            super().__init__(value)
        elif isinstance(value, int):
            super().__init__(float(value))
        elif isinstance(value, str):
            super().__init__(float(value))
        else:
            super().__init__(None)
            raise ValueError(f"unsupported value format: {value}")

    def __repr__(self):
        """
        Returns a string representation of the Value instance.

        Returns
        -------
        str
            a string representation of the Value instance
        """
        return f"FloatValue({self.value})"

    def __str__(self):
        """
        Returns a string representation of the value rounded to 6 decimal places.
        :return:
        """
        return f"{self.value:.6f}".rstrip("0").rstrip(".")
