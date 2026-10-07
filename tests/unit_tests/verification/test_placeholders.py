"""Contract tests for raw-code placeholder tokenizing."""

import pytest

from nnc.verification.placeholders import (
    Placeholder,
    TemplateError,
    TextSegment,
    parse_template,
)


def test_splits_text_and_placeholders():
    assert parse_template("P=?[ F([${done}] = ${ctrl.DONE}) ]") == (
        TextSegment("P=?[ F(["),
        Placeholder("done", 8),
        TextSegment("] = "),
        Placeholder("ctrl.DONE", 19),
        TextSegment(") ]"),
    )


def test_text_without_placeholders_is_one_segment():
    assert parse_template("G(true)") == (TextSegment("G(true)"),)


def test_empty_code_has_no_segments():
    assert parse_template("") == ()


def test_double_dollar_escapes_a_literal_placeholder_opening():
    assert parse_template("a $${x} ${y}") == (
        TextSegment("a ${x} "),
        Placeholder("y", 8),
    )


def test_lone_dollar_and_braces_are_text():
    assert parse_template("$x {y} $") == (TextSegment("$x {y} $"),)


@pytest.mark.parametrize(
    ("code", "message"),
    [
        ("a ${x", "Unclosed placeholder at offset 2"),
        ("${}", "Empty placeholder at offset 0"),
        ("${1x}", "Invalid placeholder name '1x' at offset 0"),
        ("${a.b.c}", "Invalid placeholder name 'a.b.c'"),
        ("${ x }", "Invalid placeholder name ' x '"),
        ("${a-b}", "Invalid placeholder name 'a-b'"),
    ],
)
def test_rejects_malformed_placeholders(code, message):
    with pytest.raises(TemplateError, match=message):
        parse_template(code)
