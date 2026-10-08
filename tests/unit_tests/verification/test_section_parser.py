"""Contract tests for parsing the ``verification`` YAML section."""

from pathlib import Path

import pytest

from nnc import NncSystem
from nnc.inputs.yaml.errors import YamlLocatedError
from nnc.inputs.yaml.locations import YamlLocationIndex, load_yaml_data_and_locations
from nnc.inputs.yaml.sections import YamlSectionContext
from nnc.verification import (
    InputEnvironment,
    PropertyStub,
    parse_verification_section,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "verification"


def _context(
    path: Path, data: dict, locations: YamlLocationIndex
) -> YamlSectionContext:
    return YamlSectionContext(
        source_path=path,
        import_paths=[],
        header_cache={},
        raw_data=data,
        locations=locations,
    )


def _parse_file(path: Path):
    data, locations = load_yaml_data_and_locations(path)
    return parse_verification_section(
        data.get("verification"), _context(path, data, locations)
    )


def _parse_text(tmp_path: Path, text: str):
    path = tmp_path / "model.yaml"
    path.write_text(text.lstrip(), encoding="utf-8")
    return _parse_file(path)


def test_absent_section_returns_none(tmp_path):
    assert _parse_text(tmp_path, "cells: []\n") is None


def test_parses_valid_fixture():
    config = _parse_file(FIXTURES / "input" / "fsm_counter_mc2.yaml")

    assert config.environment == {"start": InputEnvironment(range=(0.0, 1.0))}
    assert config.trace_semantics == "strict"
    assert [stub.id for stub in config.properties] == ["bounded"]
    mc2 = config.backend("mc2")
    assert [entry.id for entry in mc2.raw] == [
        "reaches_done",
        "counter_bounded",
        "done_state",
    ]
    assert mc2.raw[0].description == "The controller eventually raises done"
    assert mc2.raw[0].yaml_path == ("verification", "backends", "mc2", "raw", 0)


def test_strips_exactly_one_final_newline(tmp_path):
    config = _parse_text(
        tmp_path,
        """
verification:
  backends:
    mc2:
      raw:
        - id: block
          code: |
            P=?[ F([${x}] > 1) ]
        - id: kept
          code: "a\\n\\n"
""",
    )
    raw = config.backend("mc2").raw
    assert raw[0].code == "P=?[ F([${x}] > 1) ]"
    assert raw[1].code == "a\n"


def test_defaults(tmp_path):
    config = _parse_text(
        tmp_path,
        """
verification:
  backends:
    sva: {}
    native:
""",
    )
    assert config.trace_semantics == "strict"
    assert config.environment == {}
    assert config.properties == ()
    assert config.backend("sva").mode == "simulation"
    assert config.backend("native").mode is None
    assert config.effective_trace_semantics("sva") == "strict"


def test_backend_trace_semantics_override(tmp_path):
    config = _parse_text(
        tmp_path,
        """
verification:
  trace_semantics: strict
  backends:
    mc2:
      trace_semantics: weak
""",
    )
    assert config.effective_trace_semantics("mc2") == "weak"
    assert config.effective_trace_semantics("native") == "strict"


def test_property_stubs_keep_targets(tmp_path):
    config = _parse_text(
        tmp_path,
        """
verification:
  properties:
    - id: p1
      always: x > 0
      targets: [native, mc2]
    - id: p2
      eventually: x > 1
""",
    )
    assert config.properties == (
        PropertyStub("p1", ("native", "mc2"), ("verification", "properties", 0)),
        PropertyStub("p2", None, ("verification", "properties", 1)),
    )


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("verification: [1]\n", r"model\.yaml:1: verification must be a mapping"),
        (
            "verification:\n  run: {}\n",
            r":2: Unknown key 'run' in verification",
        ),
        (
            "verification:\n  trace_semantics: loose\n",
            r":2: verification\.trace_semantics must be one of: strict, weak",
        ),
        (
            "verification:\n  environment: [start]\n",
            r":2: verification\.environment must be a mapping",
        ),
        (
            "verification:\n  environment:\n    1: { range: [0, 1] }\n",
            r":3: verification\.environment key '1' must be an input variable name",
        ),
        (
            "verification:\n  environment:\n    true: { range: [0, 1] }\n",
            r":3: verification\.environment key 'True' must be an input variable name",
        ),
        (
            # The key is on a later line than the section, so the error must
            # point to the key itself.
            "verification:\n  environment:\n    start: { range: [0, 1] }\n"
            "    010: { range: [0, 1] }\n",
            r":4: verification\.environment key '10' must be an input variable name",
        ),
        (
            "verification:\n  environment:\n    start: { range: [1, 0] }\n",
            r":3: verification\.environment\.start\.range must be \[lo, hi\]",
        ),
        (
            "verification:\n  environment:\n    start: { range: [0, true] }\n",
            r":3: verification\.environment\.start\.range must be \[lo, hi\]",
        ),
        (
            "verification:\n  environment:\n    start:\n      distribution: uniform\n",
            r":4: verification\.environment\.start\.distribution is reserved",
        ),
        (
            "verification:\n  environment:\n    start:\n      step: 1\n",
            r":4: Unknown key 'step' in verification\.environment\.start",
        ),
        (
            "verification:\n  properties: {}\n",
            r":2: verification\.properties must be a list",
        ),
        (
            "verification:\n  properties:\n    - always: x > 0\n",
            r":3: Verification property must define 'id'",
        ),
        (
            "verification:\n  properties:\n    - id: 1bad\n",
            r":3: Verification property id must be an identifier",
        ),
        (
            "verification:\n  properties:\n    - id: p\n    - id: p\n",
            r":4: Duplicate verification property id 'p'",
        ),
        (
            "verification:\n  properties:\n    - id: p\n      targets: [prism]\n",
            r":4: Verification backend 'prism' is reserved",
        ),
        (
            "verification:\n  backends:\n    spin: {}\n",
            r":3: Verification backend 'spin' is reserved and not implemented yet",
        ),
        (
            "verification:\n  backends:\n    nusmv: {}\n",
            r":3: Unknown verification backend 'nusmv'; accepted backends: native, mc2, sva",
        ),
        (
            "verification:\n  backends:\n    native:\n      raw: []\n",
            r":4: verification\.backends\.native does not accept raw code",
        ),
        (
            "verification:\n  backends:\n    sva:\n      raw: []\n",
            r":4: verification\.backends\.sva\.raw is not supported until the SVA backend",
        ),
        (
            "verification:\n  backends:\n    sva:\n      mode: emulation\n",
            r":4: verification\.backends\.sva\.mode must be one of",
        ),
        (
            "verification:\n  backends:\n    mc2:\n      runs: 10\n",
            r":4: Unknown key 'runs' in verification\.backends\.mc2",
        ),
        (
            "verification:\n  backends:\n    mc2:\n      trace_semantics: x\n",
            r":4: verification\.backends\.mc2\.trace_semantics must be one of",
        ),
        (
            "verification:\n  backends:\n    mc2:\n      raw: {}\n",
            r":4: verification\.backends\.mc2\.raw must be a list",
        ),
        (
            "verification:\n  backends:\n    mc2:\n      raw:\n        - code: a\n",
            r":5: Raw entry must define 'id'",
        ),
        (
            "verification:\n  backends:\n    mc2:\n      raw:\n        - id: q\n",
            r":5: Raw entry must define string 'code'",
        ),
        (
            "verification:\n  backends:\n    mc2:\n      raw:\n"
            "        - id: q\n          code: a\n        - id: q\n          code: b\n",
            r":7: Duplicate mc2 raw entry id 'q'",
        ),
        (
            "verification:\n  backends:\n    mc2:\n      raw:\n"
            "        - id: q\n          code: a\n          label: x\n",
            r":7: Unknown key 'label' in mc2 raw entry",
        ),
        (
            "verification:\n  backends:\n    mc2:\n      raw:\n"
            "        - id: q\n          code: a\n          description: 3\n",
            r":7: Raw entry description must be a string",
        ),
    ],
)
def test_rejects_invalid_sections(tmp_path, text, message):
    with pytest.raises(YamlLocatedError, match=message):
        _parse_text(tmp_path, text)


def test_include_fragments_concatenate_verification_lists():
    path = FIXTURES / "include" / "main.yaml"
    raw_cache: dict = {}
    system = NncSystem.from_yaml(str(path), _raw_data_cache=raw_cache)
    data = raw_cache[system.source_path]
    config = parse_verification_section(
        data["verification"], _context(path, data, system.source_locations)
    )

    assert [stub.id for stub in config.properties] == [
        "fragment_property",
        "root_property",
    ]
    raw = config.backend("mc2").raw
    assert [entry.id for entry in raw] == ["fragment_query", "root_query"]
    fragment_line = system.source_locations.location_for(*raw[0].yaml_path)
    assert fragment_line.source_path.name == "checks.yaml"


def test_system_loading_ignores_verification_section():
    system = NncSystem.from_yaml(str(FIXTURES / "input" / "fsm_counter_mc2.yaml"))
    assert "counter" in system.variables
