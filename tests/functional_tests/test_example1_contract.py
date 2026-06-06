from pathlib import Path

from nnc import NncSystem
from nnc.parser.ast.value import FloatValue


def test_example1_contract():
    """Contract: the example1 scenario preserves the documented state trace."""
    path = Path(__file__).resolve().parent / "../fixtures/functional/example1.yaml"
    nnc = NncSystem.from_yaml(str(path))

    assert len(nnc.cells) == 1
    assert len(nnc.rules) == 4
    assert len(nnc.variables) == 5

    u = nnc.get_variable("u")
    x = nnc.get_variable("x")
    y = nnc.get_variable("y")
    e = nnc.get_variable("E")
    z = nnc.get_variable("z")

    assert u.value.value == 1
    assert x.value.value == 0
    assert y.value.value == 0
    assert e.value.value == 0
    assert z.value.value == 0

    expected = [
        (1, 0, 0, 1, 0),
        (0, 3, 1, 2, 0),
        (0, 0, 4, 3, 4),
        (0, 3, 4, 4, 4),
        (0, 6, 17, 5, 7),
        (10, 0, 0, 6, 23),
        (0, 3, 0, 7, 0),
    ]
    inputs = [1, 1, 0, 0, 10, 10, 0]

    for idx, u_value in enumerate(inputs):
        u.value = FloatValue(u_value)
        nnc.step()
        assert (
            u.value.value,
            x.value.value,
            y.value.value,
            e.value.value,
            z.value.value,
        ) == expected[idx]
