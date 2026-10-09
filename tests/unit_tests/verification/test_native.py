"""Contract tests for the native checker (spec section 6, native truth table).

Rows are positions 0..L-1. In the tables below, `p` is the condition and `t` the
trigger, given as lists of 0/1 per row.
"""

from pathlib import Path

import pytest

from nnc import NncSystem
from nnc.verification.binding import BoundVerification
from nnc.verification.config import (
    BackendSection,
    GenericProperty,
    VerificationConfig,
)
from nnc.verification.generic_properties.native import (
    COVERED,
    FAIL,
    NOT_COVERED,
    PASS,
    PENDING,
    SKIPPED,
    Obligation,
    Trace,
    VerificationError,
    check_properties,
)
from nnc.verification.generic_properties.binding import bind_property

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
    path = tmp_path_factory.mktemp("native") / "model.yaml"
    path.write_text(
        "cells:\n  - id: 1\n    contents:\n      - p = 0, t = 0, x = 0\n"
        "    output: [p]\nrules:\n  - p -> p\n",
        encoding="utf-8",
    )
    return NncSystem.from_yaml(str(path))


def _property(kind: str, **fields) -> GenericProperty:
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
    return GenericProperty(**values)


def _check(system, prop, p, t=None, semantics="strict", labels=None, extra=None):
    t = t or [0] * len(p)
    rows = [{"p": float(a), "t": float(b), "x": 0.0} for a, b in zip(p, t)]
    for row in rows:
        row.update(extra or {})
    trace = Trace(labels or list(range(len(rows))), rows)
    bound = BoundVerification(
        config=VerificationConfig(properties=(prop,)),
        raw={},
        properties=(bind_property(prop, system, system.source_locations),),
    )
    (result,) = check_properties(bound, system, trace, semantics)
    return result


def _summary(result):
    return (result.status, result.trigger_row, result.reported_row)


# --- always / never ---------------------------------------------------------


@pytest.mark.parametrize("semantics", ["strict", "weak"])
@pytest.mark.parametrize(
    ("kind", "p", "from_step", "expected"),
    [
        ("always", [1, 1, 1], 0, (PASS, None, None)),
        ("always", [1, 0, 0], 0, (FAIL, None, 1)),
        ("always", [0, 1, 1], 1, (PASS, None, None)),  # from_step skips row 0
        ("always", [0, 0], 5, (PASS, None, None)),  # empty range
        ("never", [0, 0, 0], 0, (PASS, None, None)),
        ("never", [0, 1, 1], 0, (FAIL, None, 1)),
        ("never", [1, 1], 5, (PASS, None, None)),
    ],
)
def test_always_and_never(system, semantics, kind, p, from_step, expected):
    result = _check(
        system, _property(kind, from_step=from_step), p, semantics=semantics
    )
    assert _summary(result) == expected


# --- eventually -------------------------------------------------------------


@pytest.mark.parametrize(
    ("p", "from_step", "semantics", "expected"),
    [
        ([0, 0, 1], 0, "strict", (PASS, None, None)),
        ([0, 0, 0], 0, "strict", (FAIL, None, 2)),
        ([0, 0, 0], 0, "weak", (PENDING, None, None)),
        ([1, 0, 0], 1, "strict", (FAIL, None, 2)),  # only rows >= from_step count
        ([1, 1], 5, "strict", (FAIL, None, 1)),  # empty range
        ([1, 1], 5, "weak", (PENDING, None, None)),
    ],
)
def test_eventually(system, p, from_step, semantics, expected):
    result = _check(
        system, _property("eventually", from_step=from_step), p, semantics=semantics
    )
    assert _summary(result) == expected


@pytest.mark.parametrize(
    ("p", "within", "from_step", "semantics", "expected"),
    [
        ([0, 0, 1, 0], (1, 2), 0, "strict", (PASS, None, None)),
        ([0, 0, 0, 1], (1, 2), 0, "strict", (FAIL, None, 2)),  # completed window
        ([0, 0, 0, 1], (1, 2), 0, "weak", (FAIL, None, 2)),
        ([0, 0, 0], (1, 5), 0, "strict", (FAIL, None, 2)),  # open window: last row
        ([0, 0, 0], (1, 5), 0, "weak", (PENDING, None, None)),
        ([0, 1, 0], (1, 5), 0, "weak", (PASS, None, None)),  # partly past end, seen
        ([0, 0, 0, 0, 1], (0, 1), 3, "strict", (PASS, None, None)),  # from_step
        ([1, 1], (0, 0), 5, "strict", (FAIL, None, 1)),  # empty range
        ([1, 1], (0, 0), 5, "weak", (PENDING, None, None)),
    ],
)
def test_eventually_within(system, p, within, from_step, semantics, expected):
    prop = _property("eventually_within", within=within, from_step=from_step)
    assert _summary(_check(system, prop, p, semantics=semantics)) == expected


# --- response ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("p", "t", "after", "semantics", "expected"),
    [
        ([0, 0, 1, 0], [1, 0, 0, 0], 2, "strict", (PASS, None, None)),
        ([0, 1, 0, 0], [1, 0, 0, 0], 2, "strict", (FAIL, 0, 2)),  # exactly row t+n
        ([1, 0, 0], [1, 0, 0], 0, "strict", (PASS, None, None)),  # after 0: same row
        ([0, 0, 0], [0, 0, 0], 1, "strict", (PASS, None, None)),  # no trigger
        ([0, 0, 0], [0, 1, 0], 2, "strict", (FAIL, 1, 2)),  # open: strict fails
        ([0, 0, 0], [0, 1, 0], 2, "weak", (PENDING, None, None)),
        ([0, 0, 0, 0], [1, 1, 0, 0], 2, "strict", (FAIL, 0, 2)),  # earliest detection
        ([0, 0, 1, 0, 0], [1, 1, 1, 0, 0], 2, "weak", (FAIL, 1, 3)),  # fail > pending
    ],
)
def test_response_after(system, p, t, after, semantics, expected):
    prop = _property("response_after", after=after)
    assert _summary(_check(system, prop, p, t, semantics)) == expected


def test_response_after_reports_open_obligations_when_weak(system):
    prop = _property("response_after", after=3)
    result = _check(
        system, prop, [0, 0, 0, 0], [1, 0, 1, 1], "weak", labels=[0, 10, 20, 30]
    )

    assert result.status == FAIL  # trigger at row 0 fails at row 3
    weak_open = _check(
        system, prop, [0, 0, 0, 1], [1, 0, 1, 1], "weak", labels=[0, 10, 20, 30]
    )
    assert weak_open.status == PENDING
    assert weak_open.open_obligations == (Obligation(2, 20), Obligation(3, 30))


@pytest.mark.parametrize(
    ("p", "t", "within", "semantics", "expected"),
    [
        ([0, 0, 1, 0], [1, 0, 0, 0], (1, 3), "strict", (PASS, None, None)),
        ([1, 0, 0, 0], [1, 0, 0, 0], (1, 2), "strict", (FAIL, 0, 2)),  # window t+1..t+2
        (
            [1, 0, 0],
            [1, 0, 0],
            (0, 0),
            "strict",
            (PASS, None, None),
        ),  # [0,0]: trigger row
        (
            [0, 0, 1, 0],
            [1, 0, 0, 0],
            (2, 2),
            "strict",
            (PASS, None, None),
        ),  # [n,n] = after n
        ([0, 0, 0, 0], [1, 0, 0, 0], (2, 2), "strict", (FAIL, 0, 2)),
        ([0, 0, 0], [0, 1, 0], (1, 5), "strict", (FAIL, 1, 2)),  # open window
        ([0, 0, 0], [0, 1, 0], (1, 5), "weak", (PENDING, None, None)),
        (
            [0, 0, 1],
            [0, 1, 0],
            (1, 5),
            "weak",
            (PASS, None, None),
        ),  # partly past end, seen
        # A completed window failing at the last row ties with a strict open
        # obligation (also reported at the last row): the earliest trigger wins.
        ([0, 0, 0, 0], [0, 1, 1, 0], (2, 2), "strict", (FAIL, 1, 3)),
    ],
)
def test_response_within(system, p, t, within, semantics, expected):
    prop = _property("response_within", within=within)
    assert _summary(_check(system, prop, p, t, semantics)) == expected


# --- persistence ------------------------------------------------------------


@pytest.mark.parametrize("semantics", ["strict", "weak"])
@pytest.mark.parametrize(
    ("p", "t", "after", "expected"),
    [
        ([0, 1, 1, 1], [1, 0, 0, 0], 1, (PASS, None, None)),
        ([1, 1, 0, 1], [1, 0, 0, 0], 0, (FAIL, 0, 2)),
        ([0, 0, 0, 0], [0, 0, 0, 0], 0, (PASS, None, None)),  # no trigger
        ([0, 0, 1, 0], [0, 1, 1, 0], 1, (FAIL, 1, 3)),  # earliest trigger covers row 3
        # End cases: hold throughout, even under strict semantics.
        ([0, 0, 0], [0, 0, 1], 1, (PASS, None, None)),  # trigger on last row, after 1
        ([0, 0, 0], [0, 1, 0], 2, (PASS, None, None)),  # t+n == L
        ([0, 0, 1], [0, 1, 0], 1, (PASS, None, None)),  # t+n == L-1, P true
        ([0, 0, 0], [0, 1, 0], 1, (FAIL, 1, 2)),  # t+n == L-1, P false
    ],
)
def test_persistence(system, semantics, p, t, after, expected):
    prop = _property("persistence", after=after)
    assert _summary(_check(system, prop, p, t, semantics)) == expected


# --- cover --------------------------------------------------------------------


@pytest.mark.parametrize("semantics", ["strict", "weak"])
@pytest.mark.parametrize(
    ("p", "from_step", "expected"),
    [([0, 1, 0], 0, COVERED), ([0, 0, 0], 0, NOT_COVERED), ([1, 1], 5, NOT_COVERED)],
)
def test_cover_is_not_affected_by_semantics(system, semantics, p, from_step, expected):
    result = _check(
        system, _property("cover", from_step=from_step), p, semantics=semantics
    )
    assert result.status == expected


# --- reporting, targets, and errors ---------------------------------------


def test_labels_are_reported_with_rows(system):
    result = _check(system, _property("always"), [1, 1, 0], labels=[0.0, 0.032, 0.064])

    assert (result.reported_row, result.reported_label) == (2, 0.064)


def test_properties_not_targeting_native_are_skipped_without_their_columns(system):
    native_only = _property("always", id="checked")
    mc2_only = _property("always", id="skipped", condition="x > 0", targets=("mc2",))
    bound = BoundVerification(
        config=VerificationConfig(properties=(native_only, mc2_only)),
        raw={},
        properties=tuple(
            bind_property(prop, system, system.source_locations)
            for prop in (native_only, mc2_only)
        ),
    )
    # Column `x` (used only by the skipped property) is missing from the trace.
    trace = Trace([0, 1], [{"p": 1.0, "t": 0.0}, {"p": 1.0, "t": 0.0}])

    results = check_properties(bound, system, trace, "strict")

    assert [(r.id, r.status) for r in results] == [
        ("checked", PASS),
        ("skipped", SKIPPED),
    ]


def test_missing_column_is_an_error(system):
    prop = _property("always", condition="x > 0")
    bound = BoundVerification(
        config=VerificationConfig(properties=(prop,)),
        raw={},
        properties=(bind_property(prop, system, system.source_locations),),
    )
    trace = Trace([0], [{"p": 1.0}])

    with pytest.raises(
        VerificationError, match="Property 'prop': trace has no column 'x'"
    ):
        check_properties(bound, system, trace)


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_non_finite_value_in_used_column_is_an_error(system, value):
    with pytest.raises(
        VerificationError, match=r"column 'p' is not finite at row 1 \(label 1\)"
    ):
        _check(system, _property("always"), [1, value])


def test_evaluation_error_names_property_role_row_and_label(system):
    prop = _property("always", condition="sqrt(p) >= 0")

    with pytest.raises(
        VerificationError,
        match=r"Property 'prop': evaluating the 'always' condition at row 1 "
        r"\(label 5\) failed: Error evaluating sqrt",
    ):
        _check(system, prop, [1, -1], labels=[0, 5])


@pytest.mark.parametrize(
    ("labels", "rows", "message"),
    [
        ([], [], "Trace has no rows"),
        ([0, 1], [{"p": 1.0}], "Trace has 2 labels but 1 rows"),
        ([0, 0], [{"p": 1.0}, {"p": 1.0}], "strictly increasing"),
        ([1, 0], [{"p": 1.0}, {"p": 1.0}], "strictly increasing"),
        ([0, float("nan")], [{"p": 1.0}, {"p": 1.0}], "label at row 1 is not finite"),
        ([0, 1], [{"p": 1.0}, {"q": 1.0}], "row 1 does not have the same columns"),
    ],
)
def test_trace_invariants(labels, rows, message):
    with pytest.raises(VerificationError, match=message):
        Trace(labels, rows)


def _bound(system, prop, **config):
    return BoundVerification(
        config=VerificationConfig(properties=(prop,), **config),
        raw={},
        properties=(bind_property(prop, system, system.source_locations),),
    )


def test_semantics_default_to_the_global_setting(system):
    bound = _bound(system, _property("eventually"), trace_semantics="weak")
    trace = Trace([0], [{"p": 0.0, "t": 0.0, "x": 0.0}])

    assert check_properties(bound, system, trace)[0].status == PENDING


def test_native_backend_trace_semantics_overrides_the_global_setting(system):
    bound = _bound(
        system,
        _property("eventually"),
        trace_semantics="strict",
        backends={"native": BackendSection(name="native", trace_semantics="weak")},
    )
    trace = Trace([0], [{"p": 0.0, "t": 0.0, "x": 0.0}])

    assert check_properties(bound, system, trace)[0].status == PENDING


def test_explicit_trace_semantics_must_be_valid(system):
    bound = _bound(system, _property("eventually"))
    trace = Trace([0], [{"p": 0.0, "t": 0.0, "x": 0.0}])

    with pytest.raises(VerificationError, match="trace_semantics must be one of"):
        check_properties(bound, system, trace, "lenient")


@pytest.mark.parametrize(
    ("p", "t", "expected"),
    [
        # Trigger at row 0 is before from_step and ignored (it would fail at row 1).
        ([0, 0, 0, 1], [1, 0, 1, 0], (PASS, None, None)),
        # A trigger exactly at from_step opens an obligation.
        ([0, 0, 0, 0], [0, 0, 1, 0], (FAIL, 2, 3)),
    ],
)
def test_triggers_before_from_step_are_ignored(system, p, t, expected):
    prop = _property("response_after", after=1, from_step=2)
    assert _summary(_check(system, prop, p, t)) == expected


REFERENCES = (
    Path(__file__).resolve().parents[2] / "fixtures" / "verification" / "references"
)


@pytest.mark.parametrize(
    ("mode", "level", "expected"),
    [(1.0, 3.0, PASS), (1.0, 2.0, FAIL), (0.0, 3.0, FAIL)],
)
def test_fsm_states_and_imported_columns(mode, level, expected):
    system = NncSystem.from_yaml(str(REFERENCES / "root.yaml"))
    # ctrl.ALERT is the constant 1 (no column); `sensed` aliases sensor0.level.
    prop = _property("always", condition="mode == ctrl.ALERT && sensed > LIMIT")
    trace = Trace([0], [{"mode": mode, "sensor0__level": level}])

    (result,) = check_properties(_bound(system, prop), system, trace, "strict")
    assert result.status == expected
