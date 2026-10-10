"""Configuration objects for TENNCell Webots controller generation."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class WebotsCsvConfig:
    """Describe optional CSV logging emitted by the Webots controller.

    Args:
        file: File path passed to ``open()`` by the generated controller.
        variables: TENNCell variables written as CSV columns after each step.
        include_step: Whether to prepend a generated ``_step`` column.
        include_time: Whether to prepend a generated ``_time`` column using
            ``robot.getTime()``.
        include_initial: Whether to write the initial variable snapshot before
            the Webots controller loop.
        delimiter: CSV delimiter used by the generated logger.
        precision: Optional fixed decimal precision for numeric CSV values.
    """

    file: str
    variables: list[str]
    include_step: bool = False
    include_time: bool = False
    include_initial: bool = False
    delimiter: str = ","
    precision: int | None = None


@dataclass(slots=True)
class WebotsBindingConfig:
    """Describe one TENNCell variable bound to a Webots device.

    Args:
        device: Webots device name passed to ``robot.getDevice()``, or
            ``None`` for a virtual device that ``webots.code.setup`` puts into
            ``devices`` (the controller does not call ``getDevice``).
        read_method: Optional method called on the device to read a TENNCell input.
        write_method: Optional method called on the device to write a TENNCell
            output or initialization value.

    Validation assumptions:
        At least one method must be present. The Webots transformer validates
        that TENNCell input variables have a read method and output/init variables
        have a write method before code generation.
    """

    device: str | None
    read_method: str | None = None
    write_method: str | None = None


CODE_POINTS = ("module", "setup", "before_step", "after_step", "shutdown")


@dataclass(slots=True)
class WebotsCodeBlock:
    """User Python code pasted at one insertion point of the controller.

    Args:
        text: The code, dedented, without trailing blank lines.
        source: ``inline`` or the file path as written in YAML (for the
            marker comments).
    """

    text: str
    source: str


@dataclass(slots=True)
class WebotsConfig:
    """Webots controller generation settings parsed from the YAML section.

    Args:
        controller_name: Human-readable controller name used in generated
            comments and diagnostics.
        timestep: Optional fixed Webots timestep. When omitted, generated code
            calls ``robot.getBasicTimeStep()``.
        bindings: Mapping from TENNCell variable names to Webots device bindings.
        init: One-time initialization values written before the controller loop.
        csv: Optional CSV logging configuration.
        code: User code by insertion point (``CODE_POINTS``); points without
            code are absent.
        warnings: Located parse warnings (for example a binding method that
            is an expression), reported by the transformer.
        where: ``"file:line: "`` prefixes of YAML paths under ``webots``
            (the section, bindings, init entries, CSV variables), for errors
            found later by the transformer.

    Validation assumptions:
        The Webots YAML parser supplies normalized special values such as
        ``inf`` and ``nan``. The transformer validates that bindings and init
        entries reference variables present in the resolved TENNCell model.
    """

    controller_name: str
    timestep: int | None = None
    bindings: dict[str, WebotsBindingConfig] = field(default_factory=dict)
    init: dict[str, object] = field(default_factory=dict)
    csv: WebotsCsvConfig | None = None
    code: dict[str, WebotsCodeBlock] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    where: dict[tuple[str, ...], str] = field(default_factory=dict)

    def at(self, *path: str) -> str:
        """``"file:line: "`` of a YAML path under ``webots`` (for example
        ``("bindings", "x")``), falling back to its parents, or ``""``."""
        for end in range(len(path), -1, -1):
            location = self.where.get(path[:end])
            if location:
                return location
        return ""
