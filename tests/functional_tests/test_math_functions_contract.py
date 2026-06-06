import math
from pathlib import Path

from nnc import NncSystem
from nnc.model.rule import Rule
from nnc.parser.ast.expression import ConstantExpression
from nnc.parser.ast.value import FloatValue
from nnc.parser.ast.variable import Variable


def test_math_functions_contract():
    """Contract: the math-functions scenario preserves initialization and step semantics."""
    path = (
        Path(__file__).resolve().parent / "../fixtures/functional/math_functions.yaml"
    )
    nnc = NncSystem.from_yaml(str(path))

    assert len(nnc.cells) == 1
    assert len(nnc.rules) == 6

    x = nnc.get_variable("x")
    y = nnc.get_variable("y")
    z = nnc.get_variable("z")
    a = nnc.get_variable("a")
    b = nnc.get_variable("b")
    c = nnc.get_variable("c")
    trig_result = nnc.get_variable("trigResult")
    power_result = nnc.get_variable("powerResult")
    nested_result = nnc.get_variable("nestedResult")
    standard_func_result = nnc.get_variable("standardFuncResult")
    complex_result = nnc.get_variable("complexResult")
    step = nnc.get_variable("step")

    assert x.value.value == 2.0
    assert y.value.value == 3.0
    assert z.value.value == 4.0

    assert abs(a.value.value - math.sin(2.0)) < 1e-10
    assert abs(b.value.value - math.pow(3.0, 2)) < 1e-10
    assert abs(c.value.value - (math.sin(2.0) + math.pow(3.0, 2))) < 1e-10

    assert trig_result.value.value == 0.0
    assert power_result.value.value == 0.0
    assert nested_result.value.value == 0.0
    assert standard_func_result.value.value == 0.0
    assert complex_result.value.value == 0.0
    assert step.value.value == 0.0

    x_orig = x.value.value
    y_orig = y.value.value
    z_orig = z.value.value
    a_orig = a.value.value
    b_orig = b.value.value
    c_orig = c.value.value

    expected_trig = math.sin(x_orig) * math.cos(y_orig)
    expected_power = math.pow(a_orig, b_orig)
    expected_nested = math.sqrt(
        math.pow(math.sin(x_orig), 2) + math.pow(math.cos(y_orig), 2)
    )
    expected_standard = max(x_orig, y_orig, z_orig) - min(x_orig, y_orig, z_orig)
    expected_complex = math.sqrt(c_orig * c_orig + z_orig * z_orig) + round(math.pi)

    nnc.step()

    assert x.value.value == 0.0
    assert y.value.value == 0.0
    assert z.value.value == 0.0
    assert a.value.value == 0.0
    assert b.value.value == 0.0
    assert c.value.value == 0.0
    assert step.value.value == 1.0
    assert abs(trig_result.value.value - expected_trig) < 1e-10
    assert abs(power_result.value.value - expected_power) < 1e-10
    assert abs(nested_result.value.value - expected_nested) < 1e-10
    assert abs(standard_func_result.value.value - expected_standard) < 1e-10
    assert abs(complex_result.value.value - expected_complex) < 1e-10

    expected_trig_step2 = math.sin(0.0) * math.cos(0.0)
    expected_power_step2 = math.pow(0.0, 0.0)
    expected_nested_step2 = math.sqrt(
        math.pow(math.sin(0.0), 2) + math.pow(math.cos(0.0), 2)
    )
    expected_standard_step2 = max(0.0, 0.0, 0.0) - min(0.0, 0.0, 0.0)
    expected_complex_step2 = math.sqrt(0.0 * 0.0 + 0.0 * 0.0) + round(math.pi)

    trig_result_after_step1 = trig_result.value.value
    power_result_after_step1 = power_result.value.value
    nested_result_after_step1 = nested_result.value.value
    standard_func_result_after_step1 = standard_func_result.value.value
    complex_result_after_step1 = complex_result.value.value

    nnc.step()

    assert step.value.value == 2.0
    assert (
        abs(trig_result.value.value - (trig_result_after_step1 + expected_trig_step2))
        < 1e-10
    )
    assert (
        abs(
            power_result.value.value - (power_result_after_step1 + expected_power_step2)
        )
        < 1e-10
    )
    assert (
        abs(
            nested_result.value.value
            - (nested_result_after_step1 + expected_nested_step2)
        )
        < 1e-10
    )
    assert (
        abs(
            standard_func_result.value.value
            - (standard_func_result_after_step1 + expected_standard_step2)
        )
        < 1e-10
    )
    assert (
        abs(
            complex_result.value.value
            - (complex_result_after_step1 + expected_complex_step2)
        )
        < 1e-10
    )

    unused_var = Variable("unused", FloatValue(42.0))
    nnc.variables[unused_var.name] = unused_var

    new_rule = Rule(
        consumer=trig_result,
        producer=ConstantExpression(FloatValue(5.0)),
        guard=nnc.rules[0].guard,
    )
    nnc.add_rule(new_rule)

    trig_result_before_step3 = trig_result.value.value

    nnc.step()

    assert unused_var.value.value == 42.0
    expected_trig_result_summed = trig_result_before_step3 + 0.0 + 5.0
    assert abs(trig_result.value.value - expected_trig_result_summed) < 1e-10
