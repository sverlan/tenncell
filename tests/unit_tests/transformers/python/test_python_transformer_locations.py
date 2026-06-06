from pathlib import Path

import pytest

from nnc.inputs.yaml.errors import YamlLocatedError
from nnc.model.system import NncSystem
from nnc.transformers.python_transformer import PythonTransformer


def test_transform_wraps_backend_errors_with_yaml_location():
    transformer = PythonTransformer()
    system = NncSystem()
    system.source_path = Path("sample.yaml")

    class Locations:
        def first_line_under(self, *prefix):
            return 7

    system.locations = Locations()

    def boom(*args, **kwargs):
        raise ValueError("boom")

    transformer._emit_variable_initializers = boom

    with pytest.raises(YamlLocatedError, match=r"sample\.yaml:7: boom"):
        transformer.transform(system)
