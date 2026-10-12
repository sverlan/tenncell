"""Verilog configuration errors: inconsistent boundary bindings and malformed
``verilog`` sections.

A small error table (inline YAML by design): each case is a minimal root model
whose ``verilog`` section is rejected with a message naming the problem.
"""

from pathlib import Path

import pytest

from nnc.cli_transform import _collect_import_closure, _parse_verilog_configs
from nnc.inputs.yaml.errors import YamlLocatedError
from nnc.model.system import NncSystem
from nnc.transformers import VerilogTransformer

_ENCODING = "real_encoding: {kind: fixed_point, signed: true, width: 16, frac_bits: 8}"
_CLOCKS = "clock: clk\n  reset: rst"
_IN = "{direction: input, kind: fixed, width: 16, signed: true}"
_OUT = "{direction: output, kind: fixed, width: 16, signed: true}"


def _external(alias: str, direction: str, target: str) -> str:
    """An external module (inline schema) whose port ``p`` is connected to
    the root variable ``target``."""
    return (
        f"    {alias}:\n      schema:\n        name: ext_{alias}\n        ports:\n"
        "          - {name: clk, direction: input, width: 1, signed: false}\n"
        f"          - {{name: p, direction: {direction}, kind: fixed, width: 16, "
        "signed: true}\n"
        f"      connections: {{clk: clk, p: {target}}}\n"
    )


def _model(
    *,
    inputs="u",
    outputs="y",
    extra_cells="",
    ports=None,
    externals="",
    imports="",
    verilog_extra="",
):
    """Root model text: variables u (input) and y (output) by default."""
    variables = {name: 0 for name in (*inputs.split(), *outputs.split()) if name}
    contents = "\n".join(f"      - {name} = 0" for name in dict.fromkeys(variables))
    port_lines = "".join(
        f"    {name}: {spec}\n" for name, spec in (ports or {}).items()
    )
    return (
        "module:\n  name: root\n"
        f"{imports}"
        "verilog:\n"
        f"  {_CLOCKS}\n  {_ENCODING}\n"
        + (f"  ports:\n{port_lines}" if ports is not None else "")
        + (f"  externals:\n{externals}" if externals else "")
        + verilog_extra
        + f"cells:\n  - id: 1\n    contents:\n{contents}\n{extra_cells}"
        + (f"    input: [{', '.join(inputs.split())}]\n" if inputs else "")
        + (f"    output: [{', '.join(outputs.split())}]\n" if outputs else "")
        + "rules: []\n"
    )


def _transform(tmp_path: Path, text: str) -> str:
    path = tmp_path / "root.yaml"
    path.write_text(text, encoding="utf-8")
    cache: dict = {}
    system = NncSystem.from_yaml(
        str(path), import_paths=[str(tmp_path)], _raw_data_cache=cache
    )
    transformer = VerilogTransformer(
        _parse_verilog_configs(_collect_import_closure(system), cache, [str(tmp_path)])
    )
    return transformer.transform(system)


CASES = {
    "variable both input and output (inferred ports)": (
        _model(inputs="x", outputs="x"),
        "Verilog port 'x' cannot be both an input and an output",
    ),
    "input missing from ports": (
        _model(ports={"y": _OUT}),
        "Input variable 'u' must be described in verilog.ports or verilog.externals",
    ),
    "input in ports and external outputs": (
        _model(ports={"u": _IN, "y": _OUT}, externals=_external("e0", "output", "u")),
        "Input variable 'u' cannot be described in both verilog.ports and verilog.externals",
    ),
    "input bound to an output port": (
        _model(ports={"u": _OUT, "y": _OUT}),
        "Input variable 'u' must be bound to an input port",
    ),
    "output missing from ports": (
        _model(ports={"u": _IN}),
        "Output variable 'y' must be described in verilog.ports or verilog.externals",
    ),
    "output in ports and external inputs": (
        _model(ports={"u": _IN, "y": _OUT}, externals=_external("e0", "input", "y")),
        "Output variable 'y' cannot be described in both verilog.ports and verilog.externals",
    ),
    "output bound to an input port": (
        _model(ports={"u": _IN, "y": _IN}),
        "Output variable 'y' must be bound to an output port",
    ),
    "port matching no variable": (
        _model(ports={"u": _IN, "y": _OUT, "z": _OUT}),
        "Verilog port 'z' does not match any TENNCell input or output variable",
    ),
    "input driven by two external outputs": (
        _model(
            ports={"y": _OUT},
            externals=_external("e0", "output", "u") + _external("e1", "output", "u"),
        ),
        "Verilog input variable 'u' is bound more than once by external outputs",
    ),
    "output read by two external inputs": (
        _model(
            ports={"u": _IN},
            externals=_external("e0", "input", "y") + _external("e1", "input", "y"),
        ),
        "Verilog output variable 'y' is bound more than once by external inputs",
    ),
}


@pytest.mark.parametrize(("text", "message"), CASES.values(), ids=CASES.keys())
def test_inconsistent_bindings_are_rejected_naming_the_variable(
    tmp_path, text, message
):
    with pytest.raises(ValueError, match=message):
        _transform(tmp_path, text)


_NO_SCHEMA_NAME = "external schema is missing required field 'module'"


def _line_of(text: str, needle: str) -> int:
    """1-based number of the one line of ``text`` whose content is ``needle``."""
    (number,) = [
        n for n, line in enumerate(text.splitlines(), 1) if line.strip() == needle
    ]
    return number


# text, message, and the content of the line the error must point to.
PARSER_CASES = {
    "type without kind": (
        _model(
            ports={"u": _IN, "y": _OUT}, verilog_extra="  types:\n    t: {width: 8}\n"
        ),
        "verilog.types entry is missing required field 'kind'",
        "t: {width: 8}",
    ),
    "logic type without width": (
        _model(
            ports={"u": _IN, "y": _OUT},
            verilog_extra="  types:\n    t: {kind: logic}\n",
        ),
        "verilog.types entry with kind 'logic' is missing required field 'width'",
        "t: {kind: logic}",
    ),
    "externals as a list": (
        _model(ports={"u": _IN, "y": _OUT}, externals="    - e0\n"),
        r"verilog\.externals must be a mapping of instance aliases",
        "- e0",
    ),
    "external entry that is not a mapping": (
        _model(ports={"u": _IN, "y": _OUT}, externals="    e0: 3\n"),
        r"verilog\.externals entries must be mappings",
        "e0: 3",
    ),
    "external with neither header nor schema": (
        _model(
            ports={"u": _IN, "y": _OUT}, externals="    e0:\n      connections: {}\n"
        ),
        r"verilog\.externals entries must define either 'header' or 'schema'",
        "connections: {}",
    ),
    "inline schema without a module name": (
        _model(
            ports={"u": _IN, "y": _OUT},
            externals="    e0:\n      schema:\n        ports: []\n      connections: {}\n",
        ),
        _NO_SCHEMA_NAME,
        "ports: []",
    ),
}


@pytest.mark.parametrize(
    ("text", "message", "needle"), PARSER_CASES.values(), ids=PARSER_CASES.keys()
)
def test_malformed_verilog_sections_are_rejected_with_their_line(
    tmp_path, text, message, needle
):
    line = _line_of(text, needle)

    with pytest.raises(YamlLocatedError, match=rf"root\.yaml:{line}: {message}"):
        _transform(tmp_path, text)


def test_a_header_with_a_malformed_schema_is_rejected(tmp_path):
    (tmp_path / "bad.header.yaml").write_text(
        "schema:\n  ports: []\n", encoding="utf-8"
    )
    text = _model(
        ports={"u": _IN, "y": _OUT},
        externals="    e0:\n      header: bad.header.yaml\n      connections: {}\n",
    )

    line = _line_of(text, "header: bad.header.yaml")

    with pytest.raises(
        YamlLocatedError,
        match=rf"root\.yaml:{line}: Error parsing external header '.*bad\.header\.yaml':\n"
        r".*" + _NO_SCHEMA_NAME,
    ):
        _transform(tmp_path, text)


def test_an_output_driven_by_two_imports_is_rejected(tmp_path):
    (tmp_path / "child.yaml").write_text(
        "module:\n  name: child\n"
        f"verilog:\n  {_ENCODING}\n"
        "cells:\n  - id: 1\n    contents:\n      - y = 1\n    output: [y]\n"
        "rules:\n  - y -> y\n",
        encoding="utf-8",
    )
    imports = "imports:\n  - module: child.yaml\n    as: a\n  - module: child.yaml\n    as: b\n"

    with pytest.raises(
        ValueError,
        match="Verilog variable 'y' is bound more than once by imported outputs",
    ):
        _transform(
            tmp_path, _model(inputs="", outputs="y", ports={"y": _OUT}, imports=imports)
        )


def test_an_external_without_a_resolved_schema_is_rejected(tmp_path):
    # Python API: a hand-built configuration can leave the schema unresolved
    # (YAML loading always resolves it).
    path = tmp_path / "root.yaml"
    path.write_text(
        _model(ports={"u": _IN}, externals=_external("e0", "input", "y")),
        encoding="utf-8",
    )
    cache: dict = {}
    system = NncSystem.from_yaml(str(path), _raw_data_cache=cache)
    configs = _parse_verilog_configs(_collect_import_closure(system), cache, [])
    configs[system.source_path].externals[0].definition = None

    with pytest.raises(
        ValueError, match="External 'e0' is not resolved to a reusable schema"
    ):
        VerilogTransformer(configs).transform(system)


def test_the_module_encoding_is_required_by_the_export():
    from nnc.transformers.verilog.hardware_config import (
        RealEncoding,
        VerilogHardwareConfig,
    )

    encoding = RealEncoding("fixed_point", True, 16, 8)

    assert (
        VerilogHardwareConfig(real_encoding=encoding).require_real_encoding()
        is encoding
    )
    with pytest.raises(
        ValueError, match="Verilog export requires a verilog.real_encoding section"
    ):
        VerilogHardwareConfig().require_real_encoding()
