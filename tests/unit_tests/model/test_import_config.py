"""Contract tests for ImportConfig.resolved_system."""

import pytest

from nnc.inputs.yaml.module_config import ImportConfig
from nnc.model.system import NncSystem


def test_resolved_system_returns_the_loaded_child():
    child = NncSystem()

    assert ImportConfig("child.yaml", "c0", system=child).resolved_system is child


def test_resolved_system_of_an_unresolved_import_is_an_error_naming_the_alias():
    with pytest.raises(ValueError, match="Import 'c0' is not resolved"):
        ImportConfig("child.yaml", "c0").resolved_system
