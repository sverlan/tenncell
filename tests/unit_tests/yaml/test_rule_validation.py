"""YAML loader contracts for malformed top-level rule entries."""

import pytest

from nnc.model.system import NncSystem


@pytest.mark.parametrize("item, type_name", [("null", "NoneType"), ("[]", "list")])
def test_top_level_rule_items_reject_null_and_nested_lists(tmp_path, item, type_name):
    """A top-level rules entry must be a rule string or a mapping."""
    model = tmp_path / "bad_rule.yaml"
    model.write_text(f"rules:\n  - {item}\n", encoding="utf-8")

    with pytest.raises(ValueError, match=f"Unsupported rule item type: {type_name}"):
        NncSystem.from_yaml(str(model))
