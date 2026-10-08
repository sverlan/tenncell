"""Verilog expression validation and emission."""

from __future__ import annotations

from ....parser.ast import *
from ....parser.ast.expression import FunctionCallExpression
from ....model.system import NncSystem
from ..hardware_config import VerilogEncoding, VerilogLogicEncoding
from .context import VerilogEmissionContext
from .literals import emit_constant_expression, emit_constant_in_encoding


class VerilogExpressionEmitter:
    """Validate and emit Verilog expressions from TENNCell AST nodes."""

    def _validate_supported_system(self, system: NncSystem):
        """Reject TENNCell constructs that cannot be emitted as Verilog."""
        for rule in system.rules:
            self._validate_expression(rule.producer)
            self._validate_expression(rule.guard)

    def _validate_expression(self, node):
        """Validate that a TENNCell expression can be lowered to Verilog."""
        if isinstance(node, MultiplicationExpression):
            if not isinstance(node.left, ConstantExpression) and not isinstance(
                node.right, ConstantExpression
            ):
                raise ValueError(
                    "Verilog export does not support variable-by-variable multiplication"
                )
            self._validate_expression(node.left)
            self._validate_expression(node.right)
            return

        if isinstance(node, DivisionExpression):
            if not isinstance(node.right, ConstantExpression):
                raise ValueError("Verilog export does not support general division")
            self._validate_expression(node.left)
            self._validate_expression(node.right)
            return

        if isinstance(node, FunctionCallExpression):
            raise ValueError("Verilog export does not support function calls")

        recursive_nodes = (
            SumExpression,
            DifferenceExpression,
            UnaryMinusExpression,
            IntMultiplicationExpression,
            IntDivisionExpression,
            BooleanAndExpression,
            BooleanOrExpression,
            BooleanNotExpression,
            BooleanLessTestExpression,
            BooleanLessEqualTestExpression,
            BooleanGreaterTestExpression,
            BooleanGreaterEqualTestExpression,
            BooleanEqualTestExpression,
            BooleanNotEqualTestExpression,
        )
        if isinstance(node, recursive_nodes):
            for attr in ("left", "right", "expression"):
                child = getattr(node, attr, None)
                if child is not None:
                    self._validate_expression(child)
            return

        leaf_nodes = (
            ConstantExpression,
            VariableExpression,
            ReferenceExpression,
            BooleanConstantExpression,
        )
        if isinstance(node, leaf_nodes):
            return

        raise ValueError(
            f"Unsupported expression type for Verilog export: {type(node).__name__}"
        )

    def visit(self, node, ctx: VerilogEmissionContext | None = None) -> str:
        """Dispatch to the appropriate Verilog visitor for a TENNCell node."""
        method_name = f"visit_{type(node).__name__}"
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node, ctx)

    def generic_visit(self, node, ctx: VerilogEmissionContext | None = None) -> str:
        """Reject unsupported TENNCell node types during Verilog emission."""
        raise ValueError(f"Unsupported Verilog node type: {type(node).__name__}")

    def _module_encoding(self, ctx: VerilogEmissionContext) -> VerilogEncoding:
        """Return the encoding used by the current Verilog module."""
        enc = ctx.config.real_encoding
        assert enc is not None
        return enc.to_verilog_encoding()

    def _is_constant_expression(self, node) -> bool:
        """Return ``True`` when the node is a literal expression."""
        return isinstance(node, (ConstantExpression, BooleanConstantExpression))

    def _variable_signal_name(
        self, variable_name: str, ctx: VerilogEmissionContext
    ) -> str:
        """Return the signal name used for a TENNCell variable reference."""
        if variable_name in ctx.system.input_variables:
            return variable_name
        if (
            variable_name in ctx.external_output_bindings
            or variable_name in ctx.import_output_bindings
        ):
            return variable_name
        return self._state_name(variable_name)

    def _encoding_for_expression(
        self, node, ctx: VerilogEmissionContext
    ) -> VerilogEncoding:
        """Infer the native encoding of one expression node."""
        if isinstance(node, BooleanConstantExpression):
            return VerilogLogicEncoding(kind="logic", width=1, signed=False)
        if isinstance(node, ConstantExpression):
            return self._module_encoding(ctx)
        if isinstance(node, VariableExpression):
            return self._variable_expression_encoding(node.variable.name, ctx)
        if isinstance(node, ReferenceExpression):
            return self._reference_encoding(".".join(node.parts), ctx)
        if isinstance(node, UnaryMinusExpression):
            return self._encoding_for_expression(node.expression, ctx)
        if isinstance(node, IntOperationExpression):
            return self._encoding_for_expression(node.expression, ctx)
        if isinstance(
            node,
            (
                SumExpression,
                DifferenceExpression,
                MultiplicationExpression,
                DivisionExpression,
            ),
        ):
            return self._binary_operand_encoding(node.left, node.right, ctx)
        if isinstance(
            node,
            (
                BooleanAndExpression,
                BooleanOrExpression,
                BooleanNotExpression,
                BooleanLessTestExpression,
                BooleanLessEqualTestExpression,
                BooleanGreaterTestExpression,
                BooleanGreaterEqualTestExpression,
                BooleanEqualTestExpression,
                BooleanNotEqualTestExpression,
            ),
        ):
            return VerilogLogicEncoding(kind="logic", width=1, signed=False)
        return self._module_encoding(ctx)

    def _binary_operand_encoding(
        self, left, right, ctx: VerilogEmissionContext
    ) -> VerilogEncoding:
        """Choose the common encoding used by a binary operator."""
        left_is_constant = self._is_constant_expression(left)
        right_is_constant = self._is_constant_expression(right)
        left_encoding = self._encoding_for_expression(left, ctx)
        right_encoding = self._encoding_for_expression(right, ctx)

        if left_is_constant and not right_is_constant:
            return right_encoding
        if right_is_constant and not left_is_constant:
            return left_encoding
        if left_encoding == right_encoding:
            return left_encoding

        if "fixed" in {left_encoding.kind, right_encoding.kind}:
            return self._module_encoding(ctx)

        return VerilogLogicEncoding(
            kind="logic",
            width=max(left_encoding.width, right_encoding.width),
            signed=left_encoding.signed or right_encoding.signed,
        )

    def _emit_constant_in_encoding(
        self,
        value: float,
        target_encoding: VerilogEncoding,
        ctx: VerilogEmissionContext,
    ) -> str:
        return emit_constant_in_encoding(self, value, target_encoding, ctx)

    def _emit_in_encoding(
        self,
        node,
        target_encoding: VerilogEncoding,
        ctx: VerilogEmissionContext,
    ) -> str:
        """Emit one expression subtree in the requested Verilog encoding."""
        if isinstance(node, ConstantExpression):
            return self._emit_constant_in_encoding(
                node.value.value, target_encoding, ctx
            )
        if isinstance(node, BooleanConstantExpression):
            return "1'b1" if node.value else "1'b0"
        if isinstance(node, VariableExpression):
            source = self._variable_expression_encoding(node.variable.name, ctx)
            signal = self._variable_signal_name(node.variable.name, ctx)
            return self._convert_signal_by_encoding(
                signal,
                source,
                target_encoding,
                ctx,
            )
        if isinstance(node, ReferenceExpression):
            source = self._encoding_for_expression(node, ctx)
            signal = self._reference_signal(".".join(node.parts))
            return self._convert_signal_by_encoding(
                signal,
                source,
                target_encoding,
                ctx,
            )
        if isinstance(node, UnaryMinusExpression):
            return f"(-{self._emit_in_encoding(node.expression, target_encoding, ctx)})"
        if isinstance(node, SumExpression):
            return f"({self._emit_in_encoding(node.left, target_encoding, ctx)} + {self._emit_in_encoding(node.right, target_encoding, ctx)})"
        if isinstance(node, DifferenceExpression):
            return f"({self._emit_in_encoding(node.left, target_encoding, ctx)} - {self._emit_in_encoding(node.right, target_encoding, ctx)})"
        if isinstance(node, MultiplicationExpression):
            return f"({self._emit_in_encoding(node.left, target_encoding, ctx)} * {self._emit_in_encoding(node.right, target_encoding, ctx)})"
        if isinstance(node, DivisionExpression):
            return f"({self._emit_in_encoding(node.left, target_encoding, ctx)} / {self._emit_in_encoding(node.right, target_encoding, ctx)})"
        if isinstance(node, IntMultiplicationExpression):
            expr_target = self._encoding_for_expression(node.expression, ctx)
            return f"({self._emit_constant_in_encoding(float(node.constant), expr_target, ctx)} * {self._emit_in_encoding(node.expression, expr_target, ctx)})"
        if isinstance(node, IntDivisionExpression):
            expr_target = self._encoding_for_expression(node.expression, ctx)
            return f"({self._emit_in_encoding(node.expression, expr_target, ctx)} / {self._emit_constant_in_encoding(float(node.constant), expr_target, ctx)})"
        if isinstance(
            node,
            (
                BooleanAndExpression,
                BooleanOrExpression,
                BooleanNotExpression,
            ),
        ):
            return self.visit(node, ctx)
        if isinstance(
            node,
            (
                BooleanLessTestExpression,
                BooleanLessEqualTestExpression,
                BooleanGreaterTestExpression,
                BooleanGreaterEqualTestExpression,
                BooleanEqualTestExpression,
                BooleanNotEqualTestExpression,
            ),
        ):
            operand_target = self._binary_operand_encoding(node.left, node.right, ctx)
            left = self._emit_in_encoding(node.left, operand_target, ctx)
            right = self._emit_in_encoding(node.right, operand_target, ctx)
            op = node.op
            return f"({left} {op} {right})"
        return self.visit(node, ctx)

    def visit_ConstantExpression(
        self, node: ConstantExpression, ctx: VerilogEmissionContext | None = None
    ) -> str:
        """Emit a Verilog literal for a constant expression."""
        ctx = ctx or self._emission_context
        assert ctx is not None
        return emit_constant_expression(self, node.value.value, ctx)

    def visit_VariableExpression(
        self, node: VariableExpression, ctx: VerilogEmissionContext | None = None
    ) -> str:
        """Emit the Verilog expression for one TENNCell variable reference."""
        ctx = ctx or self._emission_context
        assert ctx is not None
        if node.variable.name in ctx.system.input_variables:
            return node.variable.name
        if node.variable.name in ctx.external_output_bindings:
            return node.variable.name
        if node.variable.name in ctx.import_output_bindings:
            return node.variable.name
        return self._state_name(node.variable.name)

    def visit_ReferenceExpression(
        self, node: ReferenceExpression, ctx: VerilogEmissionContext | None = None
    ) -> str:
        """Emit a Verilog reference or converted boundary signal."""
        ctx = ctx or self._emission_context
        name = ".".join(node.parts)
        signal = self._reference_signal(name)
        assert ctx is not None
        enc = ctx.config.real_encoding
        assert enc is not None
        return self._maybe_convert_signal(
            name,
            signal,
            enc.to_verilog_encoding(),
            ctx,
        )

    def visit_SumExpression(
        self, node: SumExpression, ctx: VerilogEmissionContext | None = None
    ) -> str:
        """Emit a Verilog addition expression."""
        ctx = ctx or self._emission_context
        assert ctx is not None
        target = self._binary_operand_encoding(node.left, node.right, ctx)
        return (
            f"({self._emit_in_encoding(node.left, target, ctx)} + "
            f"{self._emit_in_encoding(node.right, target, ctx)})"
        )

    def visit_DifferenceExpression(
        self, node: DifferenceExpression, ctx: VerilogEmissionContext | None = None
    ) -> str:
        """Emit a Verilog subtraction expression."""
        ctx = ctx or self._emission_context
        assert ctx is not None
        target = self._binary_operand_encoding(node.left, node.right, ctx)
        return (
            f"({self._emit_in_encoding(node.left, target, ctx)} - "
            f"{self._emit_in_encoding(node.right, target, ctx)})"
        )

    def visit_MultiplicationExpression(
        self, node: MultiplicationExpression, ctx: VerilogEmissionContext | None = None
    ) -> str:
        """Emit a fixed-point multiplication expression."""
        if not isinstance(node.left, ConstantExpression) and not isinstance(
            node.right, ConstantExpression
        ):
            raise ValueError(
                "Verilog export does not support variable-by-variable multiplication"
            )
        ctx = ctx or self._emission_context
        assert ctx is not None
        target = self._module_encoding(ctx)
        return (
            f"(({self._emit_in_encoding(node.left, target, ctx)} * "
            f"{self._emit_in_encoding(node.right, target, ctx)}) >>> FRAC_BITS)"
        )

    def visit_DivisionExpression(
        self, node: DivisionExpression, ctx: VerilogEmissionContext | None = None
    ) -> str:
        """Emit a fixed-point division expression."""
        if not isinstance(node.right, ConstantExpression):
            raise ValueError("Verilog export does not support general division")
        ctx = ctx or self._emission_context
        assert ctx is not None
        target = self._module_encoding(ctx)
        return (
            f"(({self._emit_in_encoding(node.left, target, ctx)} <<< FRAC_BITS) / "
            f"{self._emit_in_encoding(node.right, target, ctx)})"
        )

    def visit_UnaryMinusExpression(
        self, node: UnaryMinusExpression, ctx: VerilogEmissionContext | None = None
    ) -> str:
        """Emit a Verilog unary negation expression."""
        ctx = ctx or self._emission_context
        assert ctx is not None
        target = self._encoding_for_expression(node.expression, ctx)
        return f"(-{self._emit_in_encoding(node.expression, target, ctx)})"

    def visit_IntMultiplicationExpression(
        self,
        node: IntMultiplicationExpression,
        ctx: VerilogEmissionContext | None = None,
    ) -> str:
        """Emit an integer-scaled multiplication expression."""
        ctx = ctx or self._emission_context
        assert ctx is not None
        target = self._encoding_for_expression(node.expression, ctx)
        return (
            f"({self._emit_constant_in_encoding(float(node.constant), target, ctx)} * "
            f"{self._emit_in_encoding(node.expression, target, ctx)})"
        )

    def visit_IntDivisionExpression(
        self, node: IntDivisionExpression, ctx: VerilogEmissionContext | None = None
    ) -> str:
        """Emit an integer-scaled division expression."""
        ctx = ctx or self._emission_context
        assert ctx is not None
        target = self._encoding_for_expression(node.expression, ctx)
        return (
            f"({self._emit_in_encoding(node.expression, target, ctx)} / "
            f"{self._emit_constant_in_encoding(float(node.constant), target, ctx)})"
        )

    def visit_BooleanConstantExpression(
        self,
        node: BooleanConstantExpression,
        ctx: VerilogEmissionContext | None = None,
    ) -> str:
        """Emit a Verilog boolean literal."""
        return "1'b1" if node.value else "1'b0"

    def visit_BooleanAndExpression(
        self, node: BooleanAndExpression, ctx: VerilogEmissionContext | None = None
    ) -> str:
        """Emit a Verilog logical AND expression."""
        ctx = ctx or self._emission_context
        assert ctx is not None
        target = VerilogLogicEncoding(kind="logic", width=1, signed=False)
        return (
            f"({self._emit_in_encoding(node.left, target, ctx)} && "
            f"{self._emit_in_encoding(node.right, target, ctx)})"
        )

    def visit_BooleanOrExpression(
        self, node: BooleanOrExpression, ctx: VerilogEmissionContext | None = None
    ) -> str:
        """Emit a Verilog logical OR expression."""
        ctx = ctx or self._emission_context
        assert ctx is not None
        target = VerilogLogicEncoding(kind="logic", width=1, signed=False)
        return (
            f"({self._emit_in_encoding(node.left, target, ctx)} || "
            f"{self._emit_in_encoding(node.right, target, ctx)})"
        )

    def visit_BooleanNotExpression(
        self, node: BooleanNotExpression, ctx: VerilogEmissionContext | None = None
    ) -> str:
        """Emit a Verilog logical NOT expression."""
        ctx = ctx or self._emission_context
        assert ctx is not None
        target = VerilogLogicEncoding(kind="logic", width=1, signed=False)
        return f"(!{self._emit_in_encoding(node.expression, target, ctx)})"

    def visit_BooleanLessTestExpression(
        self, node: BooleanLessTestExpression, ctx: VerilogEmissionContext | None = None
    ) -> str:
        """Emit a Verilog less-than comparison."""
        ctx = ctx or self._emission_context
        assert ctx is not None
        target = self._binary_operand_encoding(node.left, node.right, ctx)
        return (
            f"({self._emit_in_encoding(node.left, target, ctx)} < "
            f"{self._emit_in_encoding(node.right, target, ctx)})"
        )

    def visit_BooleanLessEqualTestExpression(
        self,
        node: BooleanLessEqualTestExpression,
        ctx: VerilogEmissionContext | None = None,
    ) -> str:
        """Emit a Verilog less-than-or-equal comparison."""
        ctx = ctx or self._emission_context
        assert ctx is not None
        target = self._binary_operand_encoding(node.left, node.right, ctx)
        return (
            f"({self._emit_in_encoding(node.left, target, ctx)} <= "
            f"{self._emit_in_encoding(node.right, target, ctx)})"
        )

    def visit_BooleanGreaterTestExpression(
        self,
        node: BooleanGreaterTestExpression,
        ctx: VerilogEmissionContext | None = None,
    ) -> str:
        """Emit a Verilog greater-than comparison."""
        ctx = ctx or self._emission_context
        assert ctx is not None
        target = self._binary_operand_encoding(node.left, node.right, ctx)
        return (
            f"({self._emit_in_encoding(node.left, target, ctx)} > "
            f"{self._emit_in_encoding(node.right, target, ctx)})"
        )

    def visit_BooleanGreaterEqualTestExpression(
        self,
        node: BooleanGreaterEqualTestExpression,
        ctx: VerilogEmissionContext | None = None,
    ) -> str:
        """Emit a Verilog greater-than-or-equal comparison."""
        ctx = ctx or self._emission_context
        assert ctx is not None
        target = self._binary_operand_encoding(node.left, node.right, ctx)
        return (
            f"({self._emit_in_encoding(node.left, target, ctx)} >= "
            f"{self._emit_in_encoding(node.right, target, ctx)})"
        )

    def visit_BooleanEqualTestExpression(
        self,
        node: BooleanEqualTestExpression,
        ctx: VerilogEmissionContext | None = None,
    ) -> str:
        """Emit a Verilog equality comparison."""
        ctx = ctx or self._emission_context
        assert ctx is not None
        target = self._binary_operand_encoding(node.left, node.right, ctx)
        return (
            f"({self._emit_in_encoding(node.left, target, ctx)} == "
            f"{self._emit_in_encoding(node.right, target, ctx)})"
        )

    def visit_BooleanNotEqualTestExpression(
        self,
        node: BooleanNotEqualTestExpression,
        ctx: VerilogEmissionContext | None = None,
    ) -> str:
        """Emit a Verilog inequality comparison."""
        ctx = ctx or self._emission_context
        assert ctx is not None
        target = self._binary_operand_encoding(node.left, node.right, ctx)
        return (
            f"({self._emit_in_encoding(node.left, target, ctx)} != "
            f"{self._emit_in_encoding(node.right, target, ctx)})"
        )
