"""Contract tests for resolving placeholder names and binding raw entries."""

from pathlib import Path

import pytest

from nnc import NncSystem
from nnc.inputs.yaml.errors import YamlLocatedError
from nnc.inputs.yaml.locations import load_yaml_data_and_locations
from nnc.inputs.yaml.sections import YamlSectionContext
from nnc.verification import parse_verification_section
from nnc.verification.binding import bind_verification
from nnc.verification.placeholders import TextSegment
from nnc.verification.references import ResolvedReference, resolve_reference

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "verification"
REFERENCES = FIXTURES / "references"


@pytest.fixture(scope="module")
def root_system():
    return NncSystem.from_yaml(str(REFERENCES / "root.yaml"))


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("sample", ResolvedReference("sample", "variable", "sample")),
        ("mode", ResolvedReference("mode", "variable", "mode")),
        ("LIMIT", ResolvedReference("LIMIT", "constant", "LIMIT", value=2.5)),
        (
            "ctrl.ALERT",
            ResolvedReference("ctrl.ALERT", "constant", "ctrl__ALERT", value=1.0),
        ),
        (
            "ctrl__IDLE",
            ResolvedReference("ctrl__IDLE", "constant", "ctrl__IDLE", value=0.0),
        ),
        (
            "sensor0.level",
            ResolvedReference("sensor0.level", "imported", "sensor0.level"),
        ),
        ("sensor0.raw", ResolvedReference("sensor0.raw", "imported", "sensor0.raw")),
        (
            "current",
            ResolvedReference("current", "variable", "sample", alias="current"),
        ),
        (
            "sensed",
            ResolvedReference("sensed", "imported", "sensor0.level", alias="sensed"),
        ),
    ],
)
def test_resolves_each_reference_kind(root_system, name, expected):
    assert resolve_reference(name, root_system) == expected


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("missing", r"Unknown reference '\$\{missing\}'"),
        ("sensor0.hidden", r"Unknown reference '\$\{sensor0\.hidden\}'"),
        ("sensor1.level", r"Unknown reference '\$\{sensor1\.level\}'"),
        ("ctrl.MISSING", r"Unknown reference '\$\{ctrl\.MISSING\}'"),
    ],
)
def test_rejects_unknown_references(root_system, name, message):
    with pytest.raises(ValueError, match=message):
        resolve_reference(name, root_system)


def test_rejects_ambiguous_references():
    system = NncSystem.from_yaml(str(REFERENCES / "collision.yaml"))
    with pytest.raises(
        ValueError, match=r"Ambiguous reference '\$\{x\}' matches: variable, constant"
    ):
        resolve_reference("x", system)


def _bind(path: Path):
    data, locations = load_yaml_data_and_locations(path)
    context = YamlSectionContext(path, [], {}, data, locations)
    config = parse_verification_section(data["verification"], context)
    system = NncSystem.from_yaml(str(path))
    return bind_verification(config, system, locations)


def test_binds_raw_entries_of_fixture():
    bound = _bind(FIXTURES / "input" / "fsm_counter_mc2.yaml")
    entries = bound.raw["mc2"]

    assert [item.entry.id for item in entries] == [
        "reaches_done",
        "counter_bounded",
        "done_state",
    ]
    assert entries[0].segments == (
        TextSegment("P=?[ F(["),
        ResolvedReference("done", "variable", "done"),
        TextSegment("] = 1) ]"),
    )
    done_state = [
        segment
        for segment in entries[2].segments
        if isinstance(segment, ResolvedReference)
    ]
    assert done_state == [
        ResolvedReference("ctrl_state", "variable", "ctrl_state"),
        ResolvedReference("ctrl.DONE", "constant", "ctrl__DONE", value=2.0),
        ResolvedReference("finished", "variable", "done", alias="finished"),
    ]


def _write_model(tmp_path: Path, verification: str) -> Path:
    path = tmp_path / "model.yaml"
    path.write_text(
        "cells:\n"
        "  - id: 1\n"
        "    contents:\n"
        "      - x = 0\n"
        "      - u = 0\n"
        "    input: [u]\n"
        "    output: [x]\n"
        "rules:\n"
        "  - x + u -> x\n" + verification,
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize(
    ("verification", "message"),
    [
        (
            "verification:\n  environment:\n    x: { range: [0, 1] }\n",
            r"model\.yaml:12: verification\.environment\.x must name a root input variable",
        ),
        (
            "verification:\n  backends:\n    mc2:\n      raw:\n"
            '        - id: q\n          code: "F([${y}] > 0)"\n',
            r"model\.yaml:15: Raw entry 'q': Unknown reference '\$\{y\}'",
        ),
        (
            "verification:\n  backends:\n    mc2:\n      raw:\n"
            '        - id: q\n          code: "F([${x] > 0)"\n',
            r"model\.yaml:15: Raw entry 'q': Unclosed placeholder at offset 3",
        ),
    ],
)
def test_binding_errors_point_to_yaml_lines(tmp_path, verification, message):
    with pytest.raises(YamlLocatedError, match=message):
        _bind(_write_model(tmp_path, verification))


def test_binding_errors_in_included_fragments_point_to_the_fragment():
    path = FIXTURES / "include_error" / "main.yaml"
    raw_cache: dict = {}
    system = NncSystem.from_yaml(str(path), _raw_data_cache=raw_cache)
    data = raw_cache[system.source_path]
    context = YamlSectionContext(path, [], {}, data, system.source_locations)
    config = parse_verification_section(data["verification"], context)

    with pytest.raises(YamlLocatedError) as error:
        bind_verification(config, system, system.source_locations)

    assert error.value.source_path.name == "checks.yaml"
    assert error.value.line == 8
    assert "Raw entry 'fragment_query': Unknown reference '${missing}'" in str(
        error.value
    )


def test_binding_accepts_root_input_environment(tmp_path):
    bound = _bind(
        _write_model(
            tmp_path, "verification:\n  environment:\n    u: { range: [0, 1] }\n"
        )
    )
    assert bound.raw == {}
