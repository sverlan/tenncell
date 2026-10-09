"""Contract tests for the MC2 translation of generic properties (spec section 7.3).

`P` and `T` below are the rendered condition `p > 0` and trigger `t > 0`;
`N` is the MC2 negation sign U+00AC.
"""

from pathlib import Path

import pytest

from nnc import NncSystem
from nnc.verification.config import GenericProperty
from nnc.verification.generic_properties.binding import bind_property
from nnc.verification.generic_properties.mc2 import (
    translate_property,
    unsupported_reason,
)

N = "¬"
P = "([p] > 0)"
T = "([t] > 0)"

CONDITION_KEY = {
    "always": "always",
    "never": "never",
    "eventually": "eventually",
    "eventually_within": "eventually",
    "response_after": "then",
    "response_within": "then",
    "persistence": "then_always",
    "cover": "cover",
}


@pytest.fixture(scope="module")
def system(tmp_path_factory) -> NncSystem:
    path = tmp_path_factory.mktemp("mc2") / "model.yaml"
    path.write_text(
        "cells:\n  - id: 1\n    contents:\n      - p = 0, t = 0, x = 0\n"
        "    output: [p]\nrules:\n  - p -> p\n",
        encoding="utf-8",
    )
    return NncSystem.from_yaml(str(path))


def _translate(system, kind, semantics="strict", **fields):
    values = dict(
        id="prop",
        kind=kind,
        condition="p > 0",
        condition_key=CONDITION_KEY[kind],
        trigger="t > 0" if kind.startswith(("response", "persistence")) else None,
        after=None,
        within=None,
        from_step=0,
        targets=None,
        description=None,
        yaml_path=("verification", "properties", 0),
    )
    values.update(fields)
    prop = bind_property(GenericProperty(**values), system, system.source_locations)
    return translate_property(prop, semantics)


def _q(body: str) -> str:
    return f"P=?[{body}]"


def _x(k: int, formula: str) -> str:
    return "X(" * k + formula + ")" * k


def _w(k: int) -> str:
    return f"{N}({_x(k, 'true')})"


# --- kinds without triggers ---------------------------------------------------


@pytest.mark.parametrize("semantics", ["strict", "weak"])
@pytest.mark.parametrize(
    ("kind", "fields", "expected"),
    [
        ("always", {}, f"G({P})"),
        ("always", {"from_step": 2}, f"({_w(2)} V {_x(2, f'G({P})')})"),
        ("never", {}, f"G({N}({P}))"),
        ("never", {"from_step": 1}, f"({_w(1)} V X(G({N}({P}))))"),
        ("eventually", {}, f"F({P})"),
        ("eventually", {"from_step": 2}, _x(2, f"F({P})")),
        ("cover", {}, f"F({P})"),
        ("cover", {"from_step": 1}, f"X(F({P}))"),
    ],
)
def test_unbounded_kinds(system, semantics, kind, fields, expected):
    # Weak `eventually` cannot express pending, so MC2 checks it strictly.
    assert _translate(system, kind, semantics, **fields) == _q(expected)


@pytest.mark.parametrize(
    ("within", "from_step", "strict", "weak"),
    [
        ((0, 0), 0, P, P),
        ((1, 1), 0, f"X({P})", f"(X({P}) V {_w(1)})"),
        (
            (0, 2),
            0,
            f"({P} V X(({P} V X({P}))))",
            f"(({P} V X(({P} V X({P})))) V {_w(2)})",
        ),
        (
            (1, 2),
            1,
            f"X(X(({P} V X({P}))))",
            f"({_w(1)} V X((X(({P} V X({P}))) V {_w(2)})))",
        ),
        ((0, 0), 2, _x(2, P), f"({_w(2)} V {_x(2, P)})"),
    ],
)
def test_eventually_within(system, within, from_step, strict, weak):
    fields = {"within": within, "from_step": from_step}

    assert _translate(system, "eventually_within", "strict", **fields) == _q(strict)
    assert _translate(system, "eventually_within", "weak", **fields) == _q(weak)


# --- trigger kinds -------------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "fields", "strict", "weak"),
    [
        ("response_after", {"after": 0}, f"G(({N}({T}) V {P}))", None),
        (
            "response_after",
            {"after": 2},
            f"G(({N}({T}) V X(X({P}))))",
            f"G((({N}({T}) V X(X({P}))) V {_w(2)}))",
        ),
        ("response_within", {"within": (0, 0)}, f"G(({N}({T}) V {P}))", None),
        (
            "response_within",
            {"within": (0, 1)},
            f"G(({N}({T}) V ({P} V X({P}))))",
            f"G((({N}({T}) V ({P} V X({P}))) V {_w(1)}))",
        ),
        (
            "response_within",
            {"within": (2, 2)},
            f"G(({N}({T}) V X(X({P}))))",
            f"G((({N}({T}) V X(X({P}))) V {_w(2)}))",
        ),
        ("persistence", {"after": 0}, f"G(({N}({T}) V G({P})))", None),
        (
            "persistence",
            {"after": 1},
            f"G((({N}({T}) V {_w(1)}) V X(G({P}))))",
            None,
        ),
        (
            "response_after",
            {"after": 1, "from_step": 1},
            f"({_w(1)} V X(G(({N}({T}) V X({P})))))",
            f"({_w(1)} V X(G((({N}({T}) V X({P})) V {_w(1)}))))",
        ),
    ],
)
def test_trigger_kinds(system, kind, fields, strict, weak):
    # `None`: the weak form equals the strict one (nothing can stay open, or
    # persistence, which holds throughout under both semantics).
    assert _translate(system, kind, "strict", **fields) == _q(strict)
    assert _translate(system, kind, "weak", **fields) == _q(weak or strict)


# --- conditions ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("condition", "expected"),
    [
        ("x == 1", "([x] = 1)"),
        ("x != 1", "([x] != 1)"),
        ("!(x == 1)", f"{N}(([x] = 1))"),
        ("p > 0 && t > 0 || x != 0", "((([p] > 0) ^ ([t] > 0)) V ([x] != 0))"),
        ("p > 0 && (t > 0 || x != 0)", "(([p] > 0) ^ (([t] > 0) V ([x] != 0)))"),
        ("x + 2 * t > 3", "(([x] + (2 * [t])) > 3)"),
        ("x - t - 1 < 0", "((([x] - [t]) - 1) < 0)"),
        ("-x >= -2.5", "(-([x]) >= -(2.5))"),
        ("x / 4 <= 0.25", "(([x] / 4) <= 0.25)"),
        ("true", "true"),
        ("p > 0 || false", "(([p] > 0) V false)"),
    ],
)
def test_condition_rendering(system, condition, expected):
    assert _translate(system, "always", condition=condition) == _q(f"G({expected})")


REFERENCES = (
    Path(__file__).resolve().parents[2] / "fixtures" / "verification" / "references"
)


@pytest.mark.parametrize(
    ("condition", "expected"),
    [
        # Imported output, directly and through an alias.
        ("sensor0.level > LIMIT", "([sensor0__level] > 2.5)"),
        ("sensed > LIMIT", "([sensor0__level] > 2.5)"),
        # Alias to a local variable renders as its target; FSM state as a number.
        ("current == 1 && mode == ctrl.ALERT", "(([sample] = 1) ^ ([mode] = 1))"),
    ],
)
def test_references_render_as_columns_and_numbers(condition, expected):
    references = NncSystem.from_yaml(
        str(REFERENCES / "root.yaml"), import_paths=[str(REFERENCES)]
    )

    assert _translate(references, "always", condition=condition) == _q(f"G({expected})")


def test_function_calls_are_unsupported(system):
    values = dict(
        id="prop",
        kind="always",
        condition="abs(x) < max(p, t)",
        condition_key="always",
        trigger=None,
        after=None,
        within=None,
        from_step=0,
        targets=None,
        description=None,
        yaml_path=("verification", "properties", 0),
    )
    prop = bind_property(GenericProperty(**values), system, system.source_locations)

    assert (
        unsupported_reason(prop) == "calls abs, max; MC2 queries cannot call functions"
    )
    with pytest.raises(ValueError, match="Unsupported"):
        translate_property(prop, "strict")
