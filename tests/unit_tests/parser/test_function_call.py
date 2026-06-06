import math
import random
import pytest

from nnc.parser.ast.value.float_value import FloatValue
from nnc.parser.ast.variable import Variable
from nnc.parser.parser import parse_expression, parse_variable_assignment
from nnc.parser.ast.value.math_functions import MathFunctions
from nnc.parser.ast.expression import FunctionCallExpression, ConstantExpression


@pytest.fixture
def context_variables():
    # Set up some variables for testing
    variables = {
        "x": Variable("x", FloatValue(2.0)),
        "y": Variable("y", FloatValue(3.0)),
        "z": Variable("z", FloatValue(4.0)),
    }
    return variables


@pytest.fixture(autouse=True)
def reset_math_functions():
    # Reset the MathFunctions class before each test
    MathFunctions._functions = {}
    MathFunctions._function_arg_counts = {}
    MathFunctions.register_default_functions()
    yield
    # Clean up after test if needed
    MathFunctions._functions = {}
    MathFunctions._function_arg_counts = {}


def test_repr_and_str():
    """Test the __repr__ and __str__ methods of FunctionCallExpression"""
    expr = FunctionCallExpression("sin", [ConstantExpression(FloatValue(1.0))])
    assert (
        repr(expr)
        == "FunctionCallExpression('sin', [ConstantExpression(FloatValue(1.0))])"
    )
    assert str(expr) == "sin(1)"


def test_constant_functions(context_variables):
    """Test constant functions like pi() and e()"""
    expr = parse_expression("pi()", context_variables)
    assert math.isclose(expr.evaluate().value, math.pi)

    expr = parse_expression("e()", context_variables)
    assert math.isclose(expr.evaluate().value, math.e)


def test_unary_functions(context_variables):
    """Test unary functions like sin(x), cos(x), etc."""
    # Test with literal values
    expr = parse_expression("sin(0.5)", context_variables)
    assert math.isclose(expr.evaluate().value, math.sin(0.5))

    expr = parse_expression("cos(1.0)", context_variables)
    assert math.isclose(expr.evaluate().value, math.cos(1.0))

    expr = parse_expression("sqrt(16)", context_variables)
    assert math.isclose(expr.evaluate().value, 4.0)

    expr = parse_expression("log(10)", context_variables)
    assert math.isclose(expr.evaluate().value, math.log(10))


def test_binary_functions(context_variables):
    """Test binary functions like pow(x,y), atan2(y,x), etc."""
    expr = parse_expression("pow(2, 3)", context_variables)
    assert math.isclose(expr.evaluate().value, 8.0)

    expr = parse_expression("hypot(3, 4)", context_variables)
    assert math.isclose(expr.evaluate().value, 5.0)


def test_function_with_variables(context_variables):
    """Test functions that use variables as arguments"""
    expr = parse_expression("sin(x)", context_variables)
    assert math.isclose(expr.evaluate().value, math.sin(2.0))

    expr = parse_expression("pow(x, y)", context_variables)
    assert math.isclose(expr.evaluate().value, math.pow(2.0, 3.0))

    expr = parse_expression("sqrt(z)", context_variables)
    assert math.isclose(expr.evaluate().value, 2.0)


def test_nested_functions(context_variables):
    """Test nested function calls"""
    expr = parse_expression("sin(cos(x))", context_variables)
    assert math.isclose(expr.evaluate().value, math.sin(math.cos(2.0)))

    expr = parse_expression("pow(sin(x), 2)", context_variables)
    assert math.isclose(expr.evaluate().value, math.pow(math.sin(2.0), 2))

    # More complex nested functions
    expr = parse_expression("sqrt(pow(sin(x), 2) + pow(cos(y), 2))", context_variables)
    expected = math.sqrt(math.pow(math.sin(2.0), 2) + math.pow(math.cos(3.0), 2))
    assert math.isclose(expr.evaluate().value, expected)

    expr = parse_expression("log(abs(sin(x*y)))", context_variables)
    expected = math.log(abs(math.sin(2.0 * 3.0)))
    assert math.isclose(expr.evaluate().value, expected)

    # Nested functions with arithmetic
    expr = parse_expression("sin(x + cos(y))", context_variables)
    expected = math.sin(2.0 + math.cos(3.0))
    assert math.isclose(expr.evaluate().value, expected)

    # Triple-nested functions
    expr = parse_expression("sin(cos(sqrt(x*y)))", context_variables)
    expected = math.sin(math.cos(math.sqrt(2.0 * 3.0)))
    assert math.isclose(expr.evaluate().value, expected)


def test_function_in_expressions(context_variables):
    """Test functions within larger expressions"""
    expr = parse_expression("sin(x) + cos(y)", context_variables)
    assert math.isclose(expr.evaluate().value, math.sin(2.0) + math.cos(3.0))

    expr = parse_expression("2 * pow(x, 3) + y", context_variables)
    assert math.isclose(expr.evaluate().value, 2 * math.pow(2.0, 3) + 3.0)

    expr = parse_expression("sqrt(x*x + y*y)", context_variables)
    assert math.isclose(expr.evaluate().value, math.sqrt(2.0 * 2.0 + 3.0 * 3.0))


def test_variable_assignment_with_functions(context_variables):
    """Test assigning variables using function calls"""
    # Assign using a constant function
    vars = parse_variable_assignment("a = pi()", context_variables)
    assert math.isclose(vars["a"].value.value, math.pi)

    # Assign using a unary function with a literal
    vars = parse_variable_assignment("b = sin(0.5)", context_variables)
    assert math.isclose(vars["b"].value.value, math.sin(0.5))

    # Assign using a function with a variable
    vars = parse_variable_assignment("c = sqrt(z)", context_variables)
    assert math.isclose(vars["c"].value.value, 2.0)


def test_complex_variable_assignment(context_variables):
    """Test more complex variable assignments with functions and expressions"""
    # Add variables to context for these tests
    context_variables.update(parse_variable_assignment("a = 5", context_variables))

    # Test complex expression with functions
    vars = parse_variable_assignment(
        "b = sin(x) * cos(y) + pow(a, 2)", context_variables
    )
    expected = math.sin(2.0) * math.cos(3.0) + math.pow(5.0, 2)
    assert math.isclose(vars["b"].value.value, expected)

    # Test sequential assignments with functions
    context_variables.update(vars)  # Add b to context
    vars = parse_variable_assignment("c = sqrt(b)", context_variables)
    assert math.isclose(vars["c"].value.value, math.sqrt(expected))


def test_argument_count_validation(context_variables):
    """Test that functions are called with the correct number of arguments"""
    # Test with too few arguments
    with pytest.raises(ValueError):
        parse_expression("sin()", context_variables)

    # Test with too many arguments
    with pytest.raises(ValueError):
        parse_expression("sin(x, y)", context_variables)

    # Test with correct arguments
    expr = parse_expression("sin(x)", context_variables)
    assert isinstance(expr, FunctionCallExpression)


def test_math_functions_registration():
    """Test the MathFunctions class registration and lookup"""
    # Test known function
    arg_count = MathFunctions.get_argument_count("sin")
    assert arg_count == 1

    # Test binary function
    arg_count = MathFunctions.get_argument_count("pow")
    assert arg_count == 2

    # Test zero-argument function
    arg_count = MathFunctions.get_argument_count("pi")
    assert arg_count == 0

    # Test unknown function
    with pytest.raises(ValueError):
        MathFunctions.get_argument_count("unknown_function")

    # Test function evaluation
    result = MathFunctions.evaluate("sin", [0.5])
    assert math.isclose(result, math.sin(0.5))


def test_standard_functions(context_variables):
    """Test standard Python functions registered in MathFunctions"""
    # Test max function with variable arguments
    expr = parse_expression("max(1, 2, 3, 4, 5)", context_variables)
    assert expr.evaluate().value == 5

    # Test min function with variable arguments
    expr = parse_expression("min(1, 2, 3, 4, 5)", context_variables)
    assert expr.evaluate().value == 1

    # Test abs function
    expr = parse_expression("abs(-10)", context_variables)
    assert expr.evaluate().value == 10

    # Test round function
    expr = parse_expression("round(3.14159)", context_variables)
    assert expr.evaluate().value == 3

    # Test random function - we can only check it's in the correct range
    expr = parse_expression("random()", context_variables)
    result = expr.evaluate().value
    assert 0 <= result < 1


def test_custom_function_registration():
    """Test registering and using custom functions"""
    # Reset function registry
    MathFunctions._functions = {}
    MathFunctions._function_arg_counts = {}

    # Register a custom function
    def cube(x):
        return x * x * x

    MathFunctions.register_function("cube", cube, 1)

    # Test the function's argument count
    assert MathFunctions.get_argument_count("cube") == 1

    # Test the function's evaluation
    assert MathFunctions.evaluate("cube", [3]) == 27

    # Register a custom multi-argument function
    def weighted_sum(a, b, weight=0.5):
        return a * weight + b * (1 - weight)

    MathFunctions.register_function("weighted_sum", weighted_sum, 2)
    assert MathFunctions.evaluate("weighted_sum", [10, 20]) == 15


def test_error_handling():
    """Test error handling in the MathFunctions class"""
    # Test evaluating an unknown function
    with pytest.raises(ValueError):
        MathFunctions.evaluate("nonexistent_function", [1, 2, 3])

    # Test evaluating a function with the wrong number of arguments
    with pytest.raises(ValueError):
        # sin takes 1 argument, but we're passing 2
        MathFunctions.evaluate("sin", [1, 2])

    # Test function that throws an error during evaluation
    with pytest.raises(ValueError):
        # log of a negative number should raise an error
        MathFunctions.evaluate("log", [-1])

    # Make sure error messages are descriptive
    with pytest.raises(ValueError) as exc_info:
        MathFunctions.evaluate("log", [-1])
    assert "Error evaluating" in str(exc_info.value)

    with pytest.raises(ValueError) as exc_info:
        MathFunctions.get_argument_count("nonexistent_function")
    assert "Unknown function" in str(exc_info.value)


def test_function_registration_edge_cases():
    """Test edge cases in function registration and initialization"""
    # Reset function registry
    MathFunctions._functions = {}
    MathFunctions._function_arg_counts = {}

    # Test the initialization check in get_argument_count and evaluate
    assert len(MathFunctions._functions) == 0

    # This will trigger the initialization
    MathFunctions.get_argument_count("sin")

    # Verify functions are registered
    assert len(MathFunctions._functions) > 0
    assert "sin" in MathFunctions._functions

    # Reset again
    MathFunctions._functions = {}
    MathFunctions._function_arg_counts = {}

    # Test initialization through evaluate
    MathFunctions.evaluate("sin", [0.5])
    assert len(MathFunctions._functions) > 0

    # Test registering a function with no arg_count specified (default None)
    def test_func(x):
        return x * 2

    MathFunctions.register_function("test_func", test_func)  # No arg_count specified
    assert MathFunctions.get_argument_count("test_func") is None

    # Make sure we can call the function
    assert MathFunctions.evaluate("test_func", [5]) == 10


def test_variable_arity_functions():
    """Test functions that accept variable numbers of arguments"""
    # Test max with different argument counts
    assert MathFunctions.evaluate("max", [1, 2, 3, 4, 5]) == 5
    assert MathFunctions.evaluate("max", [5, 4, 3, 2, 1]) == 5

    # Test min with different argument counts
    assert MathFunctions.evaluate("min", [5, 4, 3, 2, 1]) == 1

    # Test round with 1 or 2 args (special case)
    # Python's round() can take either 1 or 2 args
    assert MathFunctions.evaluate("round", [3.5]) == 4

    # Register a custom function with variable arity for more coverage
    def sum_args(*args):
        return sum(args)

    MathFunctions.register_function(
        "sum_args", sum_args, None
    )  # None indicates variable arity

    assert MathFunctions.evaluate("sum_args", [1, 2, 3]) == 6
    assert MathFunctions.evaluate("sum_args", [10, 20, 30, 40]) == 100


def test_advanced_error_cases():
    """Test more advanced error cases for complete coverage"""

    # Function that raises a specific error
    def problematic_func(x):
        raise TypeError("Custom error for testing")

    MathFunctions.register_function("problematic", problematic_func, 1)

    # Test that we properly wrap the error
    with pytest.raises(ValueError) as exc_info:
        MathFunctions.evaluate("problematic", [10])
    # Check that both our error message and the original message are there
    assert "Error evaluating" in str(exc_info.value)
    assert "Custom error for testing" in str(exc_info.value)

    # Test validating argument count with None (variable arity)
    # This should NOT raise an error since None means variable arity
    MathFunctions.register_function("var_args", lambda *args: sum(args), None)

    # Should work with any number of arguments without raising an error
    MathFunctions.evaluate("var_args", [1])
    MathFunctions.evaluate("var_args", [1, 2, 3])
