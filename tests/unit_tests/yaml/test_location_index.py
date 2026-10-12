"""Contract tests for YamlLocationIndex construction."""

from pathlib import Path

from nnc.inputs.yaml.locations import YamlLocation, YamlLocationIndex

FILE = Path("model.yaml")
OTHER = Path("other.yaml")


def test_line_numbers_become_locations_of_the_index_file():
    index = YamlLocationIndex(FILE, {("cells",): 3, ("rules", 0): 9})

    assert index.location_for("cells") == YamlLocation(FILE, 3)
    assert index.line_for("rules", 0) == 9
    assert index.source_for("rules", 0) == FILE


def test_locations_keep_their_own_source_file():
    index = YamlLocationIndex(FILE, {("webots",): YamlLocation(OTHER, 4)})

    assert index.source_for("webots") == OTHER
    assert index.line_for("webots") == 4


def test_the_index_does_not_alias_the_dictionary_it_was_given():
    given = {("a",): 1}
    index = YamlLocationIndex(FILE, given)
    given[("b",)] = 2

    assert index.location_for("b") is None
    assert index == YamlLocationIndex(FILE, {("a",): 1})
