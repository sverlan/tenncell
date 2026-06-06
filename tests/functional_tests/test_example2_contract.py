from pathlib import Path

from nnc import NncSystem


def test_example2_contract():
    """Contract: the example2 scenario preserves the documented E progression."""
    path = Path(__file__).resolve().parent / "../fixtures/functional/example2.yaml"
    nnc = NncSystem.from_yaml(str(path))

    expected_values = {
        "E": [0, 1, 2, 3, 4, 5, 6, 7],
    }
    input_values = {}

    for expected_var_name in expected_values:
        assert expected_var_name in nnc.variables
        assert (
            nnc.get_variable(expected_var_name).value.value
            == expected_values[expected_var_name][0]
        )

    first_key = next(iter(expected_values), None)
    sequence_length = len(expected_values[first_key]) if first_key is not None else 0

    for i in range(1, sequence_length):
        for input_var_name, input_var_value in input_values.items():
            nnc.get_variable(input_var_name).value = input_var_value[i - 1]

        nnc.step()

        for var_name, values in expected_values.items():
            assert nnc.get_variable(var_name).value.value == values[i]
