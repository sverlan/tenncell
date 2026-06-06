from nnc.parser.ast.value import FloatValue


class SequenceTest:
    def __init__(self, nnc, expected_values, input_values):
        self.nnc = nnc
        self.expected_values = expected_values
        self.input_values = input_values

    def run(self):

        for expected_var_name in self.expected_values:
            # Check that the TENNCell contains the expected variables
            assert expected_var_name in self.nnc.variables

            # Check that the variable's value matches the expected value at time 0
            var = self.nnc.get_variable(expected_var_name)
            assert var.value == FloatValue(self.expected_values[expected_var_name][0])

        # Get the first key and array from the expected_values dictionary
        first_key, first_array = next(iter(self.expected_values.items()), (None, []))
        sequence_length = len(first_array)

        # Loop over the expected values for each variable
        for i in range(1, sequence_length):
            # update the input values
            for input_var_name, input_var_value in self.input_values.items():
                var = self.nnc.get_variable(input_var_name)
                # Input values are 0-indexed
                var.value = FloatValue(input_var_value[i - 1])

            # Step the TENNCell
            self.nnc.step()

            # Check the values of all variables
            for var_name, values in self.expected_values.items():
                var = self.nnc.get_variable(var_name)
                assert var.value == FloatValue(values[i])
