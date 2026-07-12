"""Contract tests for YAML cell-content validation helpers."""

import pytest

from nnc.inputs.yaml.lowering import register_initial_declarations


class TestCellContentsValidation:
    def test_register_initial_declarations_records_unique_variables(self):
        declarations = {}

        register_initial_declarations(declarations, ["x", "y"], 0, 0)
        register_initial_declarations(declarations, ["z"], 1, 0)

        assert declarations == {"x": (0, 0), "y": (0, 0), "z": (1, 0)}

    def test_register_initial_declarations_rejects_same_cell_redeclaration(self):
        declarations = {}

        register_initial_declarations(declarations, ["x"], 0, 0)

        with pytest.raises(
            ValueError, match="Duplicate initial declaration for variable 'x'"
        ):
            register_initial_declarations(declarations, ["x"], 0, 1)

    @pytest.mark.parametrize(
        ("initial_names", "duplicate_names", "message"),
        [
            (["x"], ["x"], "Duplicate initial declaration for variable 'x'"),
            (["x", "y"], ["y"], "Duplicate initial declaration for variable 'y'"),
        ],
    )
    def test_register_initial_declarations_rejects_duplicates(
        self, initial_names, duplicate_names, message
    ):
        declarations = {}
        register_initial_declarations(declarations, initial_names, 0, 0)

        with pytest.raises(ValueError, match=message):
            register_initial_declarations(declarations, duplicate_names, 1, 0)
