from typing import Callable, Optional


class MathFunctions:
    """Class responsible for managing and evaluating mathematical functions.

    This class provides a flexible way to handle various types of mathematical functions:
    - 0-ary functions (constants like pi)
    - Unary functions (sin, cos, etc.)
    - Binary functions (pow, etc.)
    - N-ary functions (custom functions)

    Functions are evaluated dynamically and can be extended.
    """

    # Dictionary to store registered functions
    _functions: dict[str, Callable[..., float]] = {}

    # Dictionary to store the expected argument count for each function
    _function_arg_counts: dict[str, int | None] = {}

    # Canonical implementations installed by ``register_default_functions``.
    _default_functions: dict[str, Callable[..., float]] = {}
    _default_function_arg_counts: dict[str, int | None] = {}

    @classmethod
    def register_default_functions(cls):
        """Register default mathematical functions from Python's math module."""
        import math

        default_names: set[str] = set()

        # Register constants (0-ary functions)
        for name in ["pi", "e"]:
            if hasattr(math, name):
                cls.register_function(name, lambda name=name: getattr(math, name), 0)
                default_names.add(name)
            else:
                pass  # pragma: no cover

        # Register common unary functions
        for name in [
            "sin",
            "cos",
            "tan",
            "asin",
            "acos",
            "atan",
            "sinh",
            "cosh",
            "tanh",
            "exp",
            "log",
            "log10",
            "sqrt",
            "ceil",
            "floor",
            "abs",
            "degrees",
            "radians",
        ]:
            if hasattr(math, name):
                cls.register_function(name, getattr(math, name), 1)
                default_names.add(name)

        # Register binary/n-ary functions
        for name in ["pow", "atan2", "hypot"]:
            if hasattr(math, name):
                cls.register_function(name, getattr(math, name), 2)
                default_names.add(name)
            else:
                pass  # pragma: no cover

        # Register variadic functions
        # for name in ['gcd', 'lcm']:
        #    if hasattr(math, name):
        #        # These technically take at least 2 args but can take more
        #        cls.register_function(name, getattr(math, name), None)  # None indicates variable arguments

        # Register standard functions (not from math)
        cls.register_function("max", max, None)  # Variable arguments
        cls.register_function("min", min, None)  # Variable arguments
        cls.register_function(
            "round", round, 1
        )  # round(x) or round(x, n) - here we register for 1 arg
        cls.register_function("abs", abs, 1)  # abs(x)
        cls.register_function(
            "random", lambda: __import__("random").random(), 0
        )  # random()
        default_names.update({"max", "min", "round", "abs", "random"})
        cls._default_functions = {name: cls._functions[name] for name in default_names}
        cls._default_function_arg_counts = {
            name: cls._function_arg_counts[name] for name in default_names
        }

    @classmethod
    def register_function(
        cls, name: str, func: Callable, arg_count: Optional[int] = None
    ):
        """Register a new function.

        Args:
            name: The name of the function to register
            func: The callable function implementation
            arg_count: Expected number of arguments, or None for variable-argument functions
        """
        cls._functions[name] = func
        cls._function_arg_counts[name] = arg_count

    @classmethod
    def _is_default_function(cls, name: str) -> bool:
        """Return whether a name still has its canonical default implementation."""
        return cls._functions.get(name) is cls._default_functions.get(
            name
        ) and cls._function_arg_counts.get(
            name
        ) == cls._default_function_arg_counts.get(name)

    @classmethod
    def get_argument_count(cls, function_name: str) -> Optional[int]:
        """Get the expected argument count for a function.

        Args:
            function_name: The name of the function

        Returns:
            The expected number of arguments, or None if the function accepts variable arguments

        Raises:
            ValueError: If the function is unknown
        """
        # Initialize default functions if not already done
        if not cls._functions:
            cls.register_default_functions()

        if function_name not in cls._function_arg_counts:
            raise ValueError(f"Unknown function: {function_name}")

        return cls._function_arg_counts[function_name]

    @classmethod
    def evaluate(cls, function_name: str, arguments: list[float]) -> float:
        """Evaluate a function with the given arguments.

        Args:
            function_name: The name of the function to evaluate
            arguments: List of argument values

        Returns:
            The result of the function evaluation

        Raises:
            ValueError: If the function is unknown or evaluation fails
        """
        # Initialize default functions if not already done
        if not cls._functions:
            cls.register_default_functions()

        if function_name not in cls._functions:
            raise ValueError(f"Unknown function: {function_name}")

        # Validate the number of arguments
        expected_arg_count = cls.get_argument_count(function_name)
        if expected_arg_count is not None and len(arguments) != expected_arg_count:
            raise ValueError(
                f"Function {function_name} expects {expected_arg_count} arguments, got {len(arguments)}"
            )

        try:
            function = cls._functions[function_name]
            return function(*arguments)
        except Exception as e:
            raise ValueError(
                f"Error evaluating {function_name}({', '.join(str(a) for a in arguments)}): {str(e)}"
            )


# Register default functions when module is loaded
MathFunctions.register_default_functions()
