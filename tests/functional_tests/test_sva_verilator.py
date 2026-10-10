"""Opt-in contract: generated SVA files pass a Verilator lint, bind included.

Set ``NNC_VERILATOR`` to the ``verilator_bin`` executable (the Perl wrapper
``verilator`` does not run everywhere). ``VERILATOR_ROOT`` defaults to
``<bin>/../share/verilator``, as in the oss-cad-suite layout.
"""

import os
import re
from pathlib import Path

import pytest
from sva_helpers import SVA_MODELS, SVA_ROOT, run_tool, write_sva_output

VERILATOR = os.environ.get("NNC_VERILATOR")

pytestmark = pytest.mark.skipif(
    not VERILATOR or not Path(VERILATOR).is_file(),
    reason="set NNC_VERILATOR to the verilator_bin executable to lint SVA files",
)

# File and module names differ by design (`<stem>_sva.sv` holds
# `<module>_sva`), so this style warning is not a finding.
ALLOWED_IN_SVA_FILES = {"DECLFILENAME"}
WARNINGS_SUMMARY = re.compile(r"%Error: Exiting due to \d+ warning\(s\)")


def _lint(top: str, sources: list[Path], *options: str):
    root = os.environ.get(
        "VERILATOR_ROOT", str(Path(VERILATOR).parent.parent / "share" / "verilator")
    )
    return run_tool(
        VERILATOR,
        ["--lint-only", *options, "--top-module", top, *map(str, sources)],
        env={"VERILATOR_ROOT": root},
    )


@pytest.mark.parametrize("model", SVA_MODELS)
def test_sva_output_passes_default_lint(tmp_path, model):
    top, sources = write_sva_output(SVA_ROOT / model, tmp_path / "out", mode="both")
    assert any(path.name.endswith("_sva_bind.sv") for path in sources)

    result = _lint(top, sources)

    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("model", SVA_MODELS)
def test_generated_sva_files_have_no_wall_warnings(tmp_path, model):
    top, sources = write_sva_output(SVA_ROOT / model, tmp_path / "out", mode="both")

    result = _lint(top, sources, "-Wall")

    output = (result.stdout + result.stderr).splitlines()
    # -Wall warnings make Verilator exit with this summary; anything else that
    # is an error (or a failure without it) is a finding.
    summary = [line for line in output if WARNINGS_SUMMARY.fullmatch(line.strip())]
    errors = [
        line
        for line in output
        if line.startswith("%Error") and not WARNINGS_SUMMARY.fullmatch(line.strip())
    ]
    assert errors == [], "\n".join(output)
    assert result.returncode == 0 or summary, "\n".join(output)
    # Warnings: only the checker and bind files are judged; the RTL is linted
    # with the default warnings above.
    findings = [
        line
        for line in output
        if line.startswith("%Warning")
        and re.search(r"_sva(_bind)?\.sv:", line)
        and not any(f"-{name}:" in line for name in ALLOWED_IN_SVA_FILES)
    ]
    assert findings == [], "\n".join(findings)
