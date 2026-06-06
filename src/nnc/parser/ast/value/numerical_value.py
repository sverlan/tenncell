from abc import ABC

from .base_value import SimpleValue


class NumericalValue(SimpleValue, ABC):
    """
    A class to represent a numerical value.

    Attributes
    ----------
    type : str
        a string representing the type of the value
    value :
        The representation of the Value

    Methods
    -------
    __init__(value):
        Constructs a Value instance from a float, int, or str.
    __str__():
        Returns a string representation of the value.
    __repr__():
        Returns a string representation of the Value instance.
    __float__():
        Returns the float value.
    __add__(other):
        Returns a new Value instance representing the sum of this value and another.
    __sub__(other):
        Returns a new Value instance representing the difference of this value and another.
    __mul__(other):
        Returns a new Value instance representing the product of this value and another.
    __floordiv__(other):
        Returns a new Value instance representing the floor division of this value by another.
    __truediv__(other):
        Returns a new Value instance representing the true division of this value by another.
    __mod__(other):
        Returns a new Value instance representing the modulus of this value by another.
    __pow__(other):
        Returns a new Value instance representing this value raised to the power of another.
    __lt__(other):
        Returns True if this value is less than another, False otherwise.
    __gt__(other):
        Returns True if this value is greater than another, False otherwise.
    __le__(other):
        Returns True if this value is less than or equal to another, False otherwise.
    __eq__(other):
        Returns True if this value is equal to another, False otherwise.
    __ne__(other):
        Returns True if this value is not equal to another, False otherwise.
    __ge__(other):
        Returns True if this value is greater than or equal to another, False otherwise.
    """

    # def __str__(self):
    #     """
    #     Returns a string representation of the value.
    #
    #     Returns
    #     -------
    #     str
    #         a string representation of the value
    #     """
    #     return self.value.__str__()
    #
    # def __repr__(self):
    #     """
    #     Returns a string representation of the Value instance.
    #
    #     Returns
    #     -------
    #     str
    #         a string representation of the Value instance
    #     """
    #     return f"NumericalValue({self.type},{self.value})"

    def __float__(self):
        """
        Returns the float value.

        Returns
        -------
        float
            the float value
        """
        return self.value

    def __add__(self, other):
        """
        Returns a new Value instance representing the sum of this value and another.

        Parameters
        ----------
        other : Value
            the other Value instance to add

        Returns
        -------
        Value
            a new Value instance representing the sum
        """
        class_type = type(self)
        return class_type(self.value.__add__(other.value))

    def __sub__(self, other):
        """
        Returns a new Value instance representing the difference of this value and another.

        Parameters
        ----------
        other : Value
            the other Value instance to subtract

        Returns
        -------
        Value
            a new Value instance representing the difference
        """
        class_type = type(self)
        return class_type(self.value.__sub__(other.value))

    def __mul__(self, other):
        """
        Returns a new Value instance representing the product of this value and another.

        Parameters
        ----------
        other : Value
            the other Value instance to multiply

        Returns
        -------
        Value
            a new Value instance representing the product
        """
        class_type = type(self)
        return class_type(self.value.__mul__(other.value))

    def __floordiv__(self, other):
        """
        Returns a new Value instance representing the floor division of this value by another.

        Parameters
        ----------
        other : Value
            the other Value instance to divide

        Returns
        -------
        Value
            a new Value instance representing the floor division
        """
        class_type = type(self)
        return class_type(self.value.__floordiv__(other.value))

    def __truediv__(self, other):
        """
        Returns a new Value instance representing the true division of this value by another.

        Parameters
        ----------
        other : Value
            the other Value instance to divide

        Returns
        -------
        Value
            a new Value instance representing the true division
        """
        class_type = type(self)
        return class_type(self.value.__truediv__(other.value))

    def __mod__(self, other):
        """
        Returns a new Value instance representing the modulus of this value by another.

        Parameters
        ----------
        other : Value
            the other Value instance to divide

        Returns
        -------
        Value
            a new Value instance representing the modulus
        """
        class_type = type(self)
        return class_type(self.value.__mod__(other.value))

    def __pow__(self, other):
        """
        Returns a new Value instance representing this value raised to the power of another.

        Parameters
        ----------
        other : Value
            the other Value instance to use as the exponent

        Returns
        -------
        Value
            a new Value instance representing the power
        """
        class_type = type(self)
        return class_type(self.value.__pow__(other.value))

    def __neg__(self):
        """
        Returns a new Value instance representing the negation of this value.

        Returns
        -------
        Value
            a new Value instance representing the negation
        """
        class_type = type(self)
        return class_type(self.value.__neg__())

    def __lt__(self, other):
        """
        Returns True if this value is less than another, False otherwise.

        Parameters
        ----------
        other : Value
            the other Value instance to compare

        Returns
        -------
        bool
            True if this value is less than the other, False otherwise
        """
        return self.value.__lt__(other.value)

    def __gt__(self, other):
        """
        Returns True if this value is greater than another, False otherwise.

        Parameters
        ----------
        other : Value
            the other Value instance to compare

        Returns
        -------
        bool
            True if this value is greater than the other, False otherwise
        """
        return self.value.__gt__(other.value)

    def __le__(self, other):
        """
        Returns True if this value is less than or equal to another, False otherwise.

        Parameters
        ----------
        other : Value
            the other Value instance to compare

        Returns
        -------
        bool
            True if this value is less than or equal to the other, False otherwise
        """
        return self.value.__le__(other.value)

    def __eq__(self, other):
        """
        Returns True if this value is equal to another, False otherwise.

        Parameters
        ----------
        other : Value
            the other Value instance to compare

        Returns
        -------
        bool
            True if this value is equal to the other, False otherwise
        """
        return self.value.__eq__(other.value)

    def __ne__(self, other):
        """
        Returns True if this value is not equal to another, False otherwise.

        Parameters
        ----------
        other : Value
            the other Value instance to compare

        Returns
        -------
        bool
            True if this value is not equal to the other, False otherwise
        """
        return self.value.__ne__(other.value)

    def __ge__(self, other):
        """
        Returns True if this value is greater than or equal to another, False otherwise.

        Parameters
        ----------
        other : Value
            the other Value instance to compare

        Returns
        -------
        bool
            True if this value is greater than or equal to the other, False otherwise
        """
        return self.value.__ge__(other.value)
