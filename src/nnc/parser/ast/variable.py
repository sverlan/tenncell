from .value import Value


class Variable:
    name: str
    value: Value

    def __init__(self, name: str, value: Value):
        self.name = name
        self.value = value

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"Variable({self.name},{self.value.__repr__()})"
