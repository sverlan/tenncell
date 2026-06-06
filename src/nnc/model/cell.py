"""Core TENNCell cell model."""

from ..parser.ast.variable import Variable


class Cell:
    """Container for a cell id and its local variables.

    Args:
        cell_id: Numeric cell identifier.
        contents: Mapping of variable names to the variables owned by the cell.
    """

    id: int
    contents: dict[str, Variable]

    def __init__(self, cell_id: int, contents: dict[str, Variable]):
        """Create a cell from an integer id and a variable mapping.

        Args:
            cell_id: Numeric cell identifier.
            contents: Mapping of variable names to the variables owned by the cell.
        """
        self.id = cell_id
        self.contents = contents
