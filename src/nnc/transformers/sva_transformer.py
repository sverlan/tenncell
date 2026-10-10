"""SVA transformer: SystemVerilog assertion files for the generated RTL.

This module is the Python API underneath ``nnc-gen -t sva``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..inputs.yaml.locations import YamlLocationIndex
from ..model.system import NncSystem
from ..verification.binding import BoundVerification
from ..verification.sva import (
    CONCURRENT,
    SOURCES_DIR,
    SvaOptions,
    SvaSelection,
    check_sources,
    copy_sources,
    select_sva,
)
from ..verification.sva_checker import emit_checker_files, options_comment
from ..verification.sva_formal import input_assumptions, sby_text
from ..verification.sva_stimulus import (
    SvaStimulusSource,
    build_stimulus,
    check_stimulus_source,
)
from ..verification.sva_testbench import BenchPort, emit_testbench
from .sva_conditions import SvaConditionRenderer
from .verilog.generation.conversions import port_declared_signed
from .verilog.hardware_config import VerilogHardwareConfig
from .verilog_transformer import (
    VerilogTransformer,
    check_distinct_rtl_file_names,
    rtl_file_name,
)

# Above this many monitor state bits, generation warns (agreed SVA plan).
STATE_WARNING_BITS = 65_536


@dataclass(frozen=True, slots=True)
class SvaOutput:
    """Files the SVA backend generates for one model.

    Args:
        files: File contents keyed by file name: the RTL closure (one ``.sv``
            per module, exactly as ``nnc-gen -t verilog`` writes it), checker,
            the bind file and the SymbiYosys file ``<stem>.sby`` when formal
            output is requested (with the liveness helper
            ``<stem>_sva_live.v`` for unbounded ``eventually``), and, with a
            stimulus source in simulation, the testbench ``<stem>_tb.sv``, its
            stimulus ``<stem>_inputs.hex`` and the decoded inputs
            ``<stem>_inputs_decoded.csv`` (both only with an input file).
        selection: The properties and raw entries the backend emits.
        warnings: Messages to show the user.
        obsolete: SVA-specific file names of this model that this run does
            not produce (testbench, stimulus, decoded inputs, bind file,
            liveness helper);
            ``write`` removes them, so files of an earlier run do not linger.
    """

    files: dict[str, str]
    selection: SvaSelection
    warnings: tuple[str, ...]
    obsolete: tuple[str, ...] = ()


class SvaTransformer:
    """Generate SVA files for a TENNCell model and its generated RTL."""

    def __init__(
        self,
        options: SvaOptions,
        verilog_configs: dict[Path, VerilogHardwareConfig],
        verification_configs: dict[Path, BoundVerification | None],
        stimulus: SvaStimulusSource | None = None,
    ) -> None:
        """Create an SVA transformer.

        Args:
            options: Generation options (mode, style, depth, sources, bound).
            verilog_configs: Verilog configs of every module in the import
                closure, keyed by source path.
            verification_configs: Bound verification configs keyed by source
                path (``None`` when a file has no ``verification`` section).
            stimulus: Input file or number of steps for the simulation
                testbench; without it no testbench is generated.
        """
        self.options = options
        self.verilog_configs = verilog_configs
        self.verification_configs = verification_configs
        self.stimulus = stimulus

    def generate(self, system: NncSystem) -> SvaOutput:
        """Generate the SVA output for a root TENNCell system.

        Args:
            system: Root system loaded from YAML.

        Returns:
            The RTL closure, the selection and the warnings.

        Raises:
            ValueError: If the system has no verification config, nothing is
                emitted, generated file names collide case-insensitively, an
                RTL signal the checker reads has a name the checker declares
                itself, the RTL cannot be generated, or, in formal modes, a
                source is named like a generated file or a file name of the
                RTL closure, checker or sources contains whitespace (the
                ``.sby`` lists them unquoted), or a witness replay is asked
                for with the concurrent style or without generic properties
                (nothing could check the replayed failure).
            VerificationError: For a stimulus source that does not fit the
                model or mode, or an input record that cannot be encoded
                (see ``build_stimulus``).
            YamlLocatedError: For a property or raw entry the backend cannot
                handle (see ``select_sva``).
        """
        from ..cli_transform import _collect_import_closure

        if system.source_path is None:
            raise ValueError("SVA export requires systems loaded from YAML files")
        if self.stimulus is not None:
            check_stimulus_source(system, self.stimulus, self.options.simulation)
        bound = self.verification_configs.get(system.source_path)
        if bound is None:
            raise ValueError(
                "No SVA verification entries found: the model has no "
                "verification section"
            )
        closure = _collect_import_closure(system)
        check_distinct_rtl_file_names(closure)
        verilog = VerilogTransformer(self.verilog_configs)
        files = {rtl_file_name(item): verilog.transform(item) for item in closure}
        locations = system.source_locations or YamlLocationIndex(system.source_path, {})
        observation = verilog.observe(system)
        selection = select_sva(
            bound,
            observation,
            self.options,
            verilog._validate_expression,
            locations,
        )
        config = self.verilog_configs[system.source_path]
        real_encoding = config.real_encoding
        assert real_encoding is not None
        assumptions, assumption_warnings = (
            input_assumptions(bound.config.environment, observation)
            if self.options.formal and self.options.style != CONCURRENT
            else ((), ())
        )
        checker = emit_checker_files(
            observation,
            selection,
            lambda value, signal: (
                verilog._encode_float(
                    value, signal.width, signal.frac_bits, signal.signed
                )
                if signal.encoding_kind == "fixed"
                else verilog._integer_literal_ref(value, signal.width, signal.signed)
            ),
            lambda value: verilog._encode_float(
                value,
                real_encoding.width,
                real_encoding.frac_bits,
                real_encoding.signed,
            ),
            SvaConditionRenderer(self.verilog_configs, system, observation),
            assumptions,
        )
        rtl_modules = {item.module_config.name for item in closure}
        checker_modules = [f"{observation.module_name}_sva"]
        if checker.live is not None:
            checker_modules.append(f"{observation.module_name}_sva_live")
        for checker_module in checker_modules:
            if checker_module in rtl_modules:
                raise ValueError(
                    f"the checker module name '{checker_module}' is already a module "
                    "of the generated RTL; rename that module (module.name)"
                )
        stem = Path(system.source_path).stem
        live_file = f"{stem}_sva_live.v"
        generated = {
            f"{stem}_sva.sv": checker.checker,
            **(
                {f"{stem}_sva_bind.sv": checker.bind}
                if checker.bind is not None
                else {}
            ),
            **({live_file: checker.live} if checker.live is not None else {}),
        }
        if self.stimulus is not None and self.options.simulation:
            if self.stimulus.witness is not None and (
                self.options.style == CONCURRENT or not selection.properties
            ):
                raise ValueError(
                    "--sva-replay checks the replayed failure with the monitor "
                    "checker: it needs the monitor style and generic properties"
                )
            stimulus = build_stimulus(system, observation, self.stimulus, bound.config)
            module = observation.module_name
            if f"{module}_tb" in rtl_modules:
                raise ValueError(
                    f"the testbench module name '{module}_tb' is already a module "
                    "of the generated RTL; rename that module (module.name)"
                )
            hex_file = f"{stem}_inputs.hex"
            header = options_comment(selection)
            generated[f"{stem}_tb.sv"] = emit_testbench(
                module=module,
                checker_module=f"{module}_sva",
                clock=observation.clock,
                reset=observation.reset,
                reset_active_high=observation.reset_active_high,
                ports=[
                    BenchPort(
                        port.verilog_name,
                        port.dir,
                        port.width,
                        port_declared_signed(port.width, port.signed),
                    )
                    for port in verilog._collect_ports(system)
                ],
                checker_ports=checker.ports,
                stimulus=stimulus,
                hex_file=hex_file,
                has_report=bool(selection.properties)
                and self.options.style != CONCURRENT,
                header=header,
            )
            if stimulus.ports:
                if stimulus.records:  # zero records: the testbench reads no file
                    generated[hex_file] = stimulus.hex_text(header)
                generated[f"{stem}_inputs_decoded.csv"] = stimulus.decoded_csv()
            stimulus_warnings = stimulus.warnings
        else:
            stimulus_warnings = ()
        if self.options.formal:
            # The .sby lists files and read_slang arguments by name, unquoted.
            spaced = sorted(
                name
                for name in [
                    *files,
                    f"{stem}_sva.sv",
                    *(path.name for path in self.options.sources),
                ]
                if any(char.isspace() for char in name)
            )
            if spaced:
                raise ValueError(
                    "formal checks need file names without whitespace (the .sby file "
                    f"lists them unquoted): {', '.join(spaced)}; rename the files"
                )
            sources = [f"{SOURCES_DIR}/{path.name}" for path in self.options.sources]
            generated[f"{stem}.sby"] = sby_text(
                options_comment(selection),
                observation.module_name,
                self.options.effective_depth,
                [*files, f"{stem}_sva.sv", f"{stem}_sva_bind.sv", *sources],
                live_file if checker.live is not None else None,
            )
            # SymbiYosys copies the files by name into one directory.
            names = [name.casefold() for name in [*files, *generated]]
            clashes = sorted(
                path.name
                for path in self.options.sources
                if path.name.casefold() in names
            )
            if clashes:
                raise ValueError(
                    "SVA sources have the names of generated files, which formal "
                    f"checks would mix up: {', '.join(clashes)}"
                )
        rtl_names = {name.casefold(): name for name in files}
        collisions = sorted(name for name in generated if name.casefold() in rtl_names)
        if collisions:
            raise ValueError(
                "SVA-specific output file names collide with generated RTL: "
                + ", ".join(collisions)
            )
        files.update(generated)
        warnings = [*selection.warnings, *assumption_warnings, *stimulus_warnings]
        if checker.control_bits > STATE_WARNING_BITS:
            warnings.append(
                f"the SVA monitors keep {checker.control_bits:,} bits of state "
                f"(more than {STATE_WARNING_BITS:,}), so simulation and formal "
                "checks may be slow; lower the after/within/from_step bounds "
                "or --sva-max-bound"
            )
        has_externals = any(
            config.externals for config in self.verilog_configs.values()
        )
        if has_externals and not self.options.sources:
            warnings.append(
                "the RTL instantiates external modules (verilog.externals); pass "
                "their sources with --sva-source so simulators and formal tools "
                "can find them"
            )
        optional = (
            f"{stem}_sva_bind.sv",
            live_file,
            f"{stem}.sby",
            f"{stem}_tb.sv",
            f"{stem}_inputs.hex",
            f"{stem}_inputs_decoded.csv",
        )
        return SvaOutput(
            files=files,
            selection=selection,
            warnings=tuple(warnings),
            obsolete=tuple(name for name in optional if name not in files),
        )

    def write(self, output: SvaOutput, out_dir: Path) -> list[Path]:
        """Write generated files and copy external sources into ``out_dir``.

        Sources are checked before anything is written. SVA-specific files of
        this model that the run does not produce (``output.obsolete``, for
        example the stimulus of an earlier ``--sva-inputs`` run) are removed.

        Args:
            output: Result of ``generate``.
            out_dir: Output directory (created if missing).

        Returns:
            Every written or copied file.

        Raises:
            SvaOptionsError: If a source is missing or two sources share a name.
        """
        check_sources(self.options.sources)
        out_dir.mkdir(parents=True, exist_ok=True)
        for name in output.obsolete:
            (out_dir / name).unlink(missing_ok=True)
        written = []
        for name, content in output.files.items():
            path = out_dir / name
            path.write_text(content, encoding="utf-8")
            written.append(path)
        written.extend(copy_sources(self.options.sources, out_dir))
        return written
