"""Tests for BaseTransformer class."""

import pytest
from abc import ABC

from nnc.transformers.base_transformer import BaseTransformer
from nnc.model.system import NncSystem


class ConcreteTransformer(BaseTransformer):
    """Concrete implementation for testing BaseTransformer."""

    def transform(self, system: NncSystem) -> str:
        """Test implementation of transform method."""
        return "test output"

    def get_file_extension(self) -> str:
        """Test implementation of get_file_extension method."""
        return ".test"


class TestBaseTransformer:
    """Test the BaseTransformer abstract base class."""

    def test_is_abstract_base_class(self):
        """Test that BaseTransformer is an abstract base class."""
        assert issubclass(BaseTransformer, ABC)

    def test_cannot_instantiate_directly(self):
        """Test that BaseTransformer cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseTransformer()

    def test_concrete_implementation(self):
        """Test that concrete implementation can be instantiated."""
        transformer = ConcreteTransformer()
        assert isinstance(transformer, BaseTransformer)

    def test_initialization(self):
        """Test transformer initialization."""
        transformer = ConcreteTransformer()
        assert transformer.output == []

    def test_reset(self):
        """Test the reset method."""
        transformer = ConcreteTransformer()
        transformer.output = ["line1", "line2"]
        transformer.reset()
        assert transformer.output == []

    def test_add_line_no_indent(self):
        """Test adding a line without indentation."""
        transformer = ConcreteTransformer()
        transformer.add_line("test line")
        assert transformer.output == ["test line"]

    def test_add_line_with_indent(self):
        """Test adding a line with indentation."""
        transformer = ConcreteTransformer()
        transformer.add_line("test line", indent=2)
        assert transformer.output == ["        test line"]

    def test_add_line_empty_line(self):
        """Test adding an empty line."""
        transformer = ConcreteTransformer()
        transformer.add_line()
        assert transformer.output == [""]

    def test_add_line_empty_line_with_indent(self):
        """Test adding an empty line with indentation."""
        transformer = ConcreteTransformer()
        transformer.add_line("", indent=1)
        assert transformer.output == ["    "]

    def test_add_multiple_lines(self):
        """Test adding multiple lines."""
        transformer = ConcreteTransformer()
        transformer.add_line("line1")
        transformer.add_line("line2", indent=1)
        transformer.add_line("line3", indent=2)

        expected = ["line1", "    line2", "        line3"]
        assert transformer.output == expected

    def test_get_output_empty(self):
        """Test get_output with empty output."""
        transformer = ConcreteTransformer()
        assert transformer.get_output() == ""

    def test_get_output_single_line(self):
        """Test get_output with single line."""
        transformer = ConcreteTransformer()
        transformer.add_line("single line")
        assert transformer.get_output() == "single line"

    def test_get_output_multiple_lines(self):
        """Test get_output with multiple lines."""
        transformer = ConcreteTransformer()
        transformer.add_line("line1")
        transformer.add_line("line2")
        transformer.add_line("line3")

        expected = "line1\nline2\nline3"
        assert transformer.get_output() == expected

    def test_concrete_methods(self):
        """Test that concrete methods work correctly."""
        transformer = ConcreteTransformer()

        # Mock system for testing
        mock_system = NncSystem()

        result = transformer.transform(mock_system)
        assert result == "test output"

        extension = transformer.get_file_extension()
        assert extension == ".test"

    def test_workflow(self):
        """Test typical workflow with the transformer."""
        transformer = ConcreteTransformer()

        # Add some content
        transformer.add_line("# Header")
        transformer.add_line("def function():", indent=0)
        transformer.add_line("return 42", indent=1)

        # Get output
        output = transformer.get_output()
        expected = "# Header\ndef function():\n    return 42"
        assert output == expected

        # Reset and verify
        transformer.reset()
        assert transformer.get_output() == ""


def test_transform_files_defaults_to_single_file():
    """The default multi-file API wraps transform() and get_file_extension()."""
    transformer = ConcreteTransformer()

    assert transformer.transform_files(NncSystem()) == {".test": "test output"}
    assert transformer.warnings == []
