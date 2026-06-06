"""YAML loader error contract tests."""

from pathlib import Path
import re
import textwrap

import pytest

from nnc.model.system import NncSystem


def write_text(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


class TestSystemErrors:
    def test_yaml_loader_cache_hit_returns_cached_system(self, tmp_path):
        system_file = tmp_path / "cached.yaml"
        write_text(
            system_file,
            """
            module:
              name: cached_demo
            cells:
              - id: 1
                contents:
                  - x = 0
            rules: []
            """,
        )

        system_cache = {}
        raw_data_cache = {}
        first = NncSystem.from_yaml(
            str(system_file), _system_cache=system_cache, _raw_data_cache=raw_data_cache
        )
        second = NncSystem.from_yaml(
            str(system_file), _system_cache=system_cache, _raw_data_cache=raw_data_cache
        )

        assert first is second

    def test_yaml_loader_module_description_sets_metadata(self, tmp_path):
        system_file = tmp_path / "described.yaml"
        write_text(
            system_file,
            """
            module:
              name: described_demo
              description: used as a comment-like note
            cells:
              - id: 1
                contents:
                  - x = 0
            rules: []
            """,
        )

        system = NncSystem.from_yaml(str(system_file))

        assert system.metadata["description"] == "used as a comment-like note"

    def test_yaml_loader_invalid_cell_id_raises(self, tmp_path):
        system_file = tmp_path / "bad_cell_id.yaml"
        write_text(
            system_file,
            """
            cells:
              - id: not-an-integer
                contents:
                  - x = 0
            rules: []
            """,
        )

        with pytest.raises(ValueError, match="Cell id must be an integer"):
            NncSystem.from_yaml(str(system_file))

    def test_yaml_assignment_error_is_wrapped(self, tmp_path):
        system_file = tmp_path / "bad_assignment.yaml"
        write_text(
            system_file,
            """
            cells:
              - id: 1
                contents:
                  - y = x + 1
            rules: []
            """,
        )

        with pytest.raises(
            ValueError,
            match=rf"{re.escape(str(system_file))}:4: Error parsing variable assignment 'y = x \+ 1'",
        ):
            NncSystem.from_yaml(str(system_file))

    def test_yaml_rule_error_is_wrapped(self, tmp_path):
        system_file = tmp_path / "bad_rule.yaml"
        write_text(
            system_file,
            """
            cells:
              - id: 1
                contents:
                  - x = 0
            rules:
              - x -> y
            """,
        )

        with pytest.raises(ValueError, match=re.escape(str(system_file))):
            NncSystem.from_yaml(str(system_file))

    def test_imported_yaml_error_keeps_child_filename_and_line(self, tmp_path):
        root_file = tmp_path / "root.yaml"
        child_file = tmp_path / "child.yaml"
        write_text(
            child_file,
            """
            constants:
              B: A + 1
              A: 2
            cells:
              - id: 1
                contents:
                  - x = 0
            rules: []
            """,
        )
        write_text(
            root_file,
            """
            imports:
              - module: child.yaml
                as: child0
            cells:
              - id: 1
                contents:
                  - y = 0
            rules: []
            """,
        )

        with pytest.raises(
            ValueError,
            match=rf"{re.escape(str(child_file))}:2: Error evaluating constant 'B'",
        ):
            NncSystem.from_yaml(str(root_file), import_paths=[str(tmp_path)])
