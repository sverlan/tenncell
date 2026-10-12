"""Contract tests for YamlLocatedError and as_yaml_located_error."""

from pathlib import Path

from nnc.inputs.yaml.errors import YamlLocatedError, as_yaml_located_error

FILE = Path("model.yaml")
OTHER = Path("other.yaml")


def test_message_has_the_location_prefix_when_a_file_is_known():
    assert str(YamlLocatedError("bad value", FILE, 7)) == "model.yaml:7: bad value"
    assert str(YamlLocatedError("bad value")) == "bad value"


def test_attach_location_sets_what_is_given_and_returns_the_error():
    error = YamlLocatedError("bad value")

    assert error.attach_location(FILE) is error
    assert (error.source_path, error.line) == (FILE, None)
    error.attach_location(line=3)
    assert (error.source_path, error.line) == (FILE, 3)
    error.attach_location(OTHER, 9)
    assert (error.source_path, error.line) == (OTHER, 9)


def test_a_plain_exception_becomes_a_located_error_keeping_its_cause():
    original = ValueError("bad value")

    located = as_yaml_located_error(original, FILE, 4)

    assert str(located) == "model.yaml:4: bad value"
    assert located.__cause__ is original


def test_a_located_error_without_a_file_gets_the_given_location():
    error = YamlLocatedError("bad value")

    assert as_yaml_located_error(error, FILE, 4) is error
    assert str(error) == "model.yaml:4: bad value"


def test_a_located_error_with_a_file_but_no_line_gets_the_given_line_only():
    error = YamlLocatedError("bad value", FILE)

    as_yaml_located_error(error, OTHER, 6)

    assert (error.source_path, error.line) == (FILE, 6)


def test_a_fully_located_error_is_left_alone():
    error = YamlLocatedError("bad value", FILE, 2)

    as_yaml_located_error(error, OTHER, 6)

    assert (error.source_path, error.line) == (FILE, 2)
