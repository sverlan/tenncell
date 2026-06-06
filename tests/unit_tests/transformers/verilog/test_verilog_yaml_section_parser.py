"""Internal contract tests for the Verilog YAML section parser."""

from pathlib import Path
import re

import pytest

from nnc.inputs.yaml.locations import load_yaml_data_and_locations
from nnc.inputs.yaml.locations import YamlLocationIndex
from nnc.inputs.yaml.sections import YamlSectionContext
from nnc.transformers.verilog.hardware_config import ExternalInstance, PortConfig
from nnc.transformers.verilog.verilog_yaml_section_parser import (
    _require_mapping,
    parse_external_header,
    parse_ports,
    parse_real_encoding,
    parse_types,
    parse_verilog_config,
    parse_verilog_section,
)


class TestVerilogYamlSectionParser:
    def test_parse_real_encoding_and_ports_cover_defaults(self):
        assert parse_ports([{"name": "clk", "direction": "input"}]) == [
            PortConfig(name="clk", dir="input")
        ]

        with pytest.raises(ValueError, match="required field 'direction'"):
            parse_ports([{"name": "missing_direction"}])

        config = parse_verilog_config(
            {
                "real_encoding": {
                    "kind": "fixed_point",
                    "signed": True,
                    "width": 8,
                    "frac_bits": 3,
                },
                "clock": "clk",
                "reset": "rst",
                "types": {"counter": {"kind": "logic", "width": 25}},
                "ports": [{"name": "out", "direction": "output", "width": 4}],
            },
        )
        assert config.clock.name == "clk"
        assert config.reset.name == "rst"
        assert config.ports[0].kind == "logic"
        assert config.types["counter"].kind == "logic"
        assert config.types["counter"].width == 25

        with pytest.raises(ValueError, match="verilog.clock must be a string"):
            parse_verilog_config({"clock": {"name": "legacy_clk"}})

        with pytest.raises(ValueError, match="verilog.reset must be a string"):
            parse_verilog_config({"reset": {"name": "legacy_rst"}})

        with pytest.raises(ValueError, match="missing required field"):
            parse_real_encoding({"kind": "fixed_point", "signed": True})

        with pytest.raises(ValueError, match="Missing required Verilog section"):
            _require_mapping(None, "real_encoding")

        with pytest.raises(ValueError, match="must be a mapping"):
            _require_mapping([], "real_encoding")

    def test_parse_types_supports_logic_and_fixed_point(self):
        types, lines = parse_types(
            {
                "counter": {
                    "kind": "logic",
                    "width": 25,
                },
                "accum": {
                    "kind": "fixed_point",
                    "width": 40,
                    "frac_bits": 10,
                    "signed": True,
                },
            }
        )
        assert types["counter"].kind == "logic"
        assert types["counter"].width == 25
        assert types["counter"].signed is False
        assert types["accum"].kind == "fixed_point"
        assert types["accum"].width == 40
        assert types["accum"].frac_bits == 10
        assert types["accum"].signed is True
        assert lines == {"counter": None, "accum": None}

        with pytest.raises(ValueError, match="unsupported kind"):
            parse_types({"bad": {"kind": "int", "width": 8}})

        with pytest.raises(ValueError, match="missing required field"):
            parse_types({"bad": {"kind": "fixed_point", "width": 8}})

    def test_parse_verilog_section_uses_header_cache(self, tmp_path):
        source_path = tmp_path / "controller.yaml"
        source_path.write_text("module: {}\nverilog: {}\n", encoding="utf-8")

        header_path = tmp_path / "header.yaml"
        header_path.write_text(
            "schema:\n  name: uart\n  ports:\n    - name: tx\n      direction: output\n",
            encoding="utf-8",
        )

        context = YamlSectionContext(
            source_path=source_path,
            import_paths=[tmp_path],
            header_cache={},
            locations=YamlLocationIndex(source_path, {}),
            raw_data={
                "module": {},
                "verilog": {
                    "real_encoding": {
                        "kind": "fixed_point",
                        "signed": True,
                        "width": 8,
                        "frac_bits": 3,
                    },
                    "externals": {
                        "uart0": {
                            "header": "header.yaml",
                            "connections": {"tx": "tx"},
                        }
                    },
                },
            },
        )

        config = parse_verilog_section(context.raw_data["verilog"], context)
        assert config.real_encoding is not None
        assert len(config.externals) == 1
        assert isinstance(config.externals[0], ExternalInstance)
        assert config.externals[0].definition is not None
        assert config.externals[0].definition.name == "uart"
        assert config.externals[0].definition.source_path == str(header_path)
        assert len(context.header_cache) == 1

        cached = parse_verilog_section(context.raw_data["verilog"], context)
        assert len(cached.externals) == 1
        assert len(context.header_cache) == 1

    def test_parse_verilog_section_reports_clock_line(self, tmp_path):
        source_path = tmp_path / "bad_clock.yaml"
        source_path.write_text(
            "module: {}\nverilog:\n  clock: {}\n  reset: rst\n",
            encoding="utf-8",
        )
        raw_data, locations = load_yaml_data_and_locations(source_path)
        context = YamlSectionContext(
            source_path=source_path,
            import_paths=[tmp_path],
            header_cache={},
            locations=locations,
            raw_data=raw_data,
        )

        with pytest.raises(
            ValueError,
            match=rf"{re.escape(str(source_path))}:3: verilog.clock must be a string",
        ):
            parse_verilog_section(context.raw_data["verilog"], context)

    def test_parse_external_header_requires_section(self, tmp_path):
        header_path = tmp_path / "bad.yaml"
        header_path.write_text("not_external: true\n", encoding="utf-8")

        with pytest.raises(
            ValueError,
            match=rf"{re.escape(str(header_path))}:1: External header must contain a 'schema' section",
        ):
            parse_external_header(header_path)
