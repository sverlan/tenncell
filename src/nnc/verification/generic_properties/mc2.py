"""Translate bound generic properties into MC2 PLTLc queries (spec section 7.3).

Bodies follow the native finite-trace semantics: ``X`` past the last row is
false, ``W_k = ¬X^k(true)`` means "the trace ends within k rows", and ``->`` is
never emitted (MC2 v2.0beta2 evaluates ``a -> X(b)`` to false).
"""

from __future__ import annotations

from ..config import (
    ALWAYS,
    COVER,
    EVENTUALLY,
    EVENTUALLY_WITHIN,
    NEVER,
    PERSISTENCE,
    RESPONSE_AFTER,
    RESPONSE_WITHIN,
)
from .binding import BoundProperty
from .conditions import ConditionSyntax, decimal_literal, render_condition

MC2 = "mc2"
NOT = "¬"

MC2_SYNTAX = ConditionSyntax(
    operators={
        "&&": "^",
        "||": "V",
        "==": "=",
        "!=": "!=",
        "<": "<",
        "<=": "<=",
        ">": ">",
        ">=": ">=",
        "+": "+",
        "-": "-",
        "*": "*",
        "/": "/",
    },
    negation=NOT,
    true="true",
    false="false",
    column=lambda name: f"[{name}]",
    literal=decimal_literal,
)


def weak_approximation(prop: BoundProperty) -> bool:
    """Return whether the weak MC2 query counts an open obligation as satisfied
    where native would report ``pending``."""
    spec = prop.property
    if spec.kind == EVENTUALLY_WITHIN:
        assert spec.within is not None
        return spec.within[1] > 0 or spec.from_step > 0
    if spec.kind == RESPONSE_AFTER:
        return bool(spec.after)
    if spec.kind == RESPONSE_WITHIN:
        assert spec.within is not None
        return spec.within[1] > 0
    return False


def unsupported_reason(prop: BoundProperty) -> str | None:
    """Return why MC2 cannot check a property, or ``None`` if it can."""
    if prop.functions:
        names = ", ".join(sorted(prop.functions))
        return f"calls {names}; MC2 queries cannot call functions"
    return None


def translate_property(prop: BoundProperty, trace_semantics: str) -> str:
    """Return the ``P=?[...]`` query for a supported generic property.

    Args:
        prop: Bound property without function calls (see ``unsupported_reason``).
        trace_semantics: ``strict`` or ``weak``.

    Returns:
        One MC2 query line.

    Raises:
        ValueError: If the property uses a construct MC2 cannot express.
    """
    spec = prop.property
    weak = trace_semantics == "weak"
    p = render_condition(prop.condition, MC2_SYNTAX, prop.states)
    t = (
        render_condition(prop.trigger, MC2_SYNTAX, prop.states)
        if prop.trigger is not None
        else None
    )
    f = spec.from_step
    kind = spec.kind
    if kind in (EVENTUALLY, COVER):
        # Weak `eventually` cannot express pending, so it is checked strictly.
        return _query(_next(f, f"F({p})"))
    if kind == EVENTUALLY_WITHIN:
        assert spec.within is not None
        a, b = spec.within
        body = _next(a, _window(p, b - a))
        if not weak:
            return _query(_next(f, body))
        return _query(_from(f, _or(body, _ends_within(b)) if b > 0 else body))
    if kind == ALWAYS:
        body = f"G({p})"
    elif kind == NEVER:
        body = f"G({NOT}({p}))"
    elif kind == RESPONSE_AFTER:
        assert t is not None and spec.after is not None
        n = spec.after
        terms = [f"{NOT}({t})", _next(n, p)]
        if weak and n > 0:
            terms.append(_ends_within(n))
        body = f"G({_or(*terms)})"
    elif kind == RESPONSE_WITHIN:
        assert t is not None and spec.within is not None
        a, b = spec.within
        terms = [f"{NOT}({t})", _next(a, _window(p, b - a))]
        if weak and b > 0:
            terms.append(_ends_within(b))
        body = f"G({_or(*terms)})"
    elif kind == PERSISTENCE:
        assert t is not None and spec.after is not None
        n = spec.after
        terms = [f"{NOT}({t})"]
        if n > 0:
            terms.append(_ends_within(n))
        terms.append(_next(n, f"G({p})"))
        body = f"G({_or(*terms)})"
    else:
        raise ValueError(f"Unknown property kind '{kind}'")
    return _query(_from(f, body))


def _query(body: str) -> str:
    return f"P=?[{body}]"


def _next(k: int, formula: str) -> str:
    """``X^k(formula)``; ``X^0`` is the formula itself."""
    return "X(" * k + formula + ")" * k


def _ends_within(k: int) -> str:
    """``W_k``: true when row ``now + k`` does not exist (``k > 0``)."""
    return f"{NOT}({_next(k, 'true')})"


def _window(p: str, width: int) -> str:
    """``p V X(p) V ... V X^width(p)``, nested as ``(p V X((p V X(p))))``."""
    formula = p
    for _ in range(width):
        formula = _or(p, f"X({formula})")
    return formula


def _from(f: int, body: str) -> str:
    """Evaluate a safety body from row ``f``; true when the trace has no row ``f``."""
    if f == 0:
        return body
    return _or(_ends_within(f), _next(f, body))


def _or(*terms: str) -> str:
    """Left-nested binary disjunction, fully parenthesized."""
    formula = terms[0]
    for term in terms[1:]:
        formula = f"({formula} V {term})"
    return formula
