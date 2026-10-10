"""Opt-in contract: generated SVA files are valid SystemVerilog for slang.

slang is a complete SystemVerilog front end (``yosys -m slang``, the
yosys-slang plugin of the oss-cad-suite). ``read_slang --ast-compilation-only``
parses and elaborates without synthesis, so it also checks the full SVA of the
concurrent style, which no local simulator runs. Set ``NNC_YOSYS`` to the
``yosys`` executable to run these tests.
"""

import os
from pathlib import Path

import pytest
from sva_helpers import SVA_MODELS, SVA_ROOT, run_tool, write_sva_output

YOSYS = os.environ.get("NNC_YOSYS")

pytestmark = pytest.mark.skipif(
    not YOSYS or not Path(YOSYS).is_file(),
    reason="set NNC_YOSYS to the yosys executable (with the slang plugin)",
)


def _slang(sources: list[Path], *options: str, live: Path | None = None):
    # Relative paths from the sources' directory: read_slang takes no quoting.
    # The liveness helper is read first with read_verilog, as in the .sby.
    base = sources[0].parent
    files = " ".join(path.relative_to(base).as_posix() for path in sources)
    flags = " ".join(options)
    helper = f"read_verilog -formal -icells {live.name}; " if live is not None else ""
    return run_tool(
        YOSYS,
        [
            "-q",
            "-m",
            "slang",
            "-p",
            f"{helper}read_slang --ast-compilation-only {flags} {files}",
        ],
        cwd=base,
    )


def test_slang_rejects_invalid_sva(tmp_path):
    # Control: the check is meaningful (`##n` cannot be followed by a property).
    bad = tmp_path / "bad.sv"
    bad.write_text(
        "module bad(input logic clk, input logic a);\n"
        "  p: assert property (@(posedge clk) a |-> ##2 always a);\nendmodule\n",
        encoding="utf-8",
    )

    assert _slang([bad]).returncode != 0


@pytest.mark.parametrize(
    ("mode", "style"),
    [("both", "monitor"), ("simulation", "monitor"), ("simulation", "concurrent")],
)
@pytest.mark.parametrize("model", SVA_MODELS)
def test_generated_sva_files_compile_in_slang(tmp_path, model, mode, style):
    if style == "concurrent" and model.endswith("weak.yaml"):
        pytest.skip("the concurrent style rejects weak semantics")
    _, sources = write_sva_output(
        SVA_ROOT / model,
        tmp_path / "out",
        mode=mode,
        style=style,
        testbench=mode == "simulation",
    )

    result = _slang(sources)

    assert result.returncode == 0, result.stdout + result.stderr
    if mode == "both":  # the formal block too, as SymbiYosys reads it
        helpers = list((tmp_path / "out").glob("*_sva_live.v"))
        formal = _slang(sources, "-D", "FORMAL", live=helpers[0] if helpers else None)
        assert formal.returncode == 0, formal.stdout + formal.stderr
