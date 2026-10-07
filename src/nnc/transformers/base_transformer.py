"""Base transformer class for converting TENNCell AST to various output formats."""

from abc import ABC, abstractmethod
from ..model.system import NncSystem


class BaseTransformer(ABC):
    """Abstract base class for transforming TENNCell systems to different output formats."""

    def __init__(self):
        self.output = []
        self.warnings: list[str] = []

    def transform_files(self, system: NncSystem) -> dict[str, str]:
        """Transform a TENNCell system into one or more output files.

        The default emits a single file using ``transform()`` and
        ``get_file_extension()``. Backends that produce several files override it.

        Args:
            system: The TENNCell system to transform

        Returns:
            Mapping from file suffix (appended to the output base name) to
            file content
        """
        return {self.get_file_extension(): self.transform(system)}

    @abstractmethod
    def transform(self, system: NncSystem) -> str:
        """Transform a TENNCell system to the target format.

        Args:
            system: The TENNCell system to transform

        Returns:
            String representation in the target format
        """
        pass  # pragma: no cover

    @abstractmethod
    def get_file_extension(self) -> str:
        """Get the file extension for the output format.

        Returns:
            File extension (e.g., '.py', '.js', '.cpp')
        """
        pass  # pragma: no cover

    def reset(self):
        """Reset the transformer state."""
        self.output = []

    def add_line(self, line: str = "", indent: int = 0):
        """Add a line to the output with optional indentation.

        Args:
            line: The line to add
            indent: Number of indentation levels (4 spaces each)
        """
        indented_line = "    " * indent + line
        self.output.append(indented_line)

    def get_output(self) -> str:
        """Get the current output as a string."""
        return "\n".join(self.output)
