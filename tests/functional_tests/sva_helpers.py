"""Shared helpers for the opt-in SVA tool tests (Icarus, Verilator)."""

import os
import subprocess
from pathlib import Path

from nnc.cli_transform import (
    _collect_import_closure,
    _parse_verification_configs,
    _parse_verilog_configs,
)
from nnc.model.system import NncSystem
from nnc.transformers import SvaTransformer
from nnc.verification.sva import SvaOptions
from nnc.verification.sva_stimulus import SvaStimulusSource

SVA_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "verification" / "sva"

# Every SVA fixture model: imports, externals, renamed ports, aliases, FSM
# constants, raw code and every monitored property kind.
SVA_MODELS = [
    "controller.yaml",
    "checker_interface/root.yaml",
    "import_closure/parent.yaml",
    "external/root.yaml",
    "monitors/monitors.yaml",
    "monitors/weak.yaml",
]

# Stub for the external module of external/root.yaml, passed as an SVA source.
UART_STUB = (
    "module uart(input logic clk, output logic ready);\n"
    "  assign ready = 1'b0;\n"
    "endmodule\n"
)


def run_tool(
    executable: str,
    args: list[str],
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
):
    """Run an oss-cad-suite tool with its bin and lib directories on PATH."""
    tool_dir = Path(executable).parent
    full_env = {
        **os.environ,
        **(env or {}),
        "PATH": os.pathsep.join(
            [str(tool_dir), str(tool_dir.parent / "lib"), os.environ["PATH"]]
        ),
    }
    return subprocess.run(
        [executable, *args],
        capture_output=True,
        text=True,
        env=full_env,
        cwd=cwd,
        timeout=300,
        check=False,
    )


def write_sva_output(
    model: Path,
    out: Path,
    mode: str = "simulation",
    style: str = "monitor",
    testbench: bool = False,
) -> tuple[str, list[Path]]:
    """Generate and write the SVA output of a fixture model.

    With ``testbench``, the testbench is generated too: on a header-only
    input file (zero records) for a model with inputs, on two steps otherwise.

    Returns:
        The root module name and the SystemVerilog sources written (RTL
        closure, checker, bind file in formal modes, testbench, copied
        external sources), without the Yosys-only liveness helper.
    """
    cache: dict = {}
    import_paths = [str(model.parent)]
    system = NncSystem.from_yaml(
        str(model), import_paths=import_paths, _raw_data_cache=cache
    )
    stub = out.parent / f"{out.name}_stub" / "uart.v"
    stub.parent.mkdir(parents=True)
    stub.write_text(UART_STUB, encoding="utf-8")
    stimulus = None
    if testbench:
        if system.input_variables:
            header = out.parent / f"{out.name}_inputs.csv"
            header.write_text(",".join(system.input_variables) + "\n", encoding="utf-8")
            stimulus = SvaStimulusSource(inputs=header)
        else:
            stimulus = SvaStimulusSource(steps=2)
    transformer = SvaTransformer(
        SvaOptions(mode=mode, style=style, sources=(stub,)),
        _parse_verilog_configs(_collect_import_closure(system), cache, import_paths),
        _parse_verification_configs([system], cache),
        stimulus,
    )
    written = transformer.write(transformer.generate(system), out)
    # The liveness helper (a Yosys $live cell) is for Yosys formal reads only.
    sources = [
        path
        for path in written
        if path.suffix in (".sv", ".v") and not path.name.endswith("_sva_live.v")
    ]
    return system.module_config.name, sources
