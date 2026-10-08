"""YAML loader that resolves plain scalars with YAML 1.2 core-schema rules.

PyYAML follows YAML 1.1, where plain ``on``/``off``/``yes``/``no`` are booleans,
``010`` is octal 8, ``1:30`` is 90, and dates become date objects. TENNCell uses
YAML 1.2 core rules instead (including ``0o17`` octal), keeping two YAML 1.1
number forms: underscores (``1_000``) and binary (``0b101``). Only the interpretation of plain values
changes; the YAML syntax is unaffected.
"""

from __future__ import annotations

import re

import yaml

_BOOL = "tag:yaml.org,2002:bool"
_NULL = "tag:yaml.org,2002:null"
_INT = "tag:yaml.org,2002:int"
_FLOAT = "tag:yaml.org,2002:float"
_REPLACED_TAGS = {
    _BOOL,
    _NULL,
    _INT,
    _FLOAT,
    "tag:yaml.org,2002:timestamp",
    "tag:yaml.org,2002:value",
}

_BOOL_PATTERN = re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$")
_NULL_PATTERN = re.compile(r"^(?:~|null|Null|NULL|)$")
_INT_PATTERN = re.compile(
    r"^[-+]?(?:0b[01][01_]*|0o[0-7][0-7_]*|0x[0-9a-fA-F][0-9a-fA-F_]*|[0-9][0-9_]*)$"
)
_FLOAT_PATTERN = re.compile(
    r"^(?:[-+]?(?:[0-9][0-9_]*\.[0-9_]*|\.[0-9][0-9_]*)(?:[eE][-+]?[0-9]+)?"
    r"|[-+]?[0-9][0-9_]*[eE][-+]?[0-9]+"
    r"|[-+]?\.(?:inf|Inf|INF)"
    r"|\.(?:nan|NaN|NAN))$"
)


class TenncellYamlLoader(yaml.SafeLoader):
    """Safe YAML loader using YAML 1.2 core rules for plain scalars."""


TenncellYamlLoader.yaml_implicit_resolvers = {
    first: [(tag, regexp) for tag, regexp in resolvers if tag not in _REPLACED_TAGS]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
TenncellYamlLoader.add_implicit_resolver(_BOOL, _BOOL_PATTERN, list("tTfF"))
TenncellYamlLoader.add_implicit_resolver(_NULL, _NULL_PATTERN, ["~", "n", "N", ""])
TenncellYamlLoader.add_implicit_resolver(_INT, _INT_PATTERN, list("-+0123456789"))
TenncellYamlLoader.add_implicit_resolver(_FLOAT, _FLOAT_PATTERN, list("-+.0123456789"))


def _construct_int(loader: yaml.SafeLoader, node: yaml.ScalarNode) -> int:
    """Build an int; a leading zero is decimal, not YAML 1.1 octal."""
    text = str(loader.construct_scalar(node)).replace("_", "")
    sign = -1 if text.startswith("-") else 1
    digits = text.lstrip("+-")
    if digits.startswith("0b"):
        return sign * int(digits[2:], 2)
    if digits.startswith("0o"):
        return sign * int(digits[2:], 8)
    if digits.startswith("0x"):
        return sign * int(digits[2:], 16)
    return sign * int(digits, 10)


TenncellYamlLoader.add_constructor(_INT, _construct_int)
