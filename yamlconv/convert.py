"""Conversion between nested config data and two textual formats.

Every function here is pure: given the same input it always returns the
same output, and none of them touch the filesystem. That is what makes
them easy to unit test and safe to compose (see cli.py for the only
place that does file I/O).

Lists are treated as opaque leaf values by flatten/unflatten rather than
being expanded into indexed keys. That keeps the mapping between the two
formats simple and lossless for the common case (scalar lists like
`tags: [a, b]`); a list containing nested dicts round-trips fine too, it
just is not addressable key-by-key the way scalar entries are.
"""

from __future__ import annotations

from typing import Any

from .yaml_format import dump_yaml, parse_yaml


def flatten(data: dict, sep: str = ".") -> dict:
    """Collapse a nested mapping into a single-level dict of dotted keys."""
    items: dict[str, Any] = {}
    _flatten_into(data, "", sep, items)
    return items


def _flatten_into(node: Any, prefix: str, sep: str, out: dict) -> None:
    if isinstance(node, dict):
        if not node:
            out[prefix] = {}
            return
        for key, value in node.items():
            new_prefix = f"{prefix}{sep}{key}" if prefix else str(key)
            _flatten_into(value, new_prefix, sep, out)
    else:
        out[prefix] = node


def unflatten(flat: dict, sep: str = ".") -> dict:
    """Rebuild a nested mapping from the dotted keys produced by flatten()."""
    root: dict = {}
    for compound_key, value in flat.items():
        if compound_key == "" and value == {}:
            continue
        parts = compound_key.split(sep)
        node = root
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
    return root


def parse_properties(text: str) -> dict:
    """Parse `key=value` lines into a flat dict. Pure function."""
    flat: dict[str, Any] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        if "=" not in line:
            continue
        key, _, raw_value = line.partition("=")
        flat[key.strip()] = _parse_properties_value(raw_value.strip())
    return flat


def dump_properties(flat: dict) -> str:
    """Render a flat dict as sorted `key=value` lines. Pure function."""
    lines = [f"{key}={_dump_properties_value(flat[key])}" for key in sorted(flat)]
    return "\n".join(lines) + ("\n" if lines else "")


def yaml_to_properties(yaml_text: str, sep: str = ".") -> str:
    """Convert nested YAML text into flat properties text."""
    data = parse_yaml(yaml_text)
    return dump_properties(flatten(data or {}, sep=sep))


def properties_to_yaml(properties_text: str, sep: str = ".") -> str:
    """Convert flat properties text into nested YAML text."""
    nested = unflatten(parse_properties(properties_text), sep=sep)
    return dump_yaml(nested)


def _parse_properties_value(raw: str) -> Any:
    if raw == "":
        return None
    if "," in raw:
        return [_coerce_scalar(part.strip()) for part in raw.split(",")]
    return _coerce_scalar(raw)


def _coerce_scalar(s: str) -> Any:
    if s.lower() == "true":
        return True
    if s.lower() == "false":
        return False
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def _dump_properties_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ",".join(_dump_properties_scalar(v) for v in value)
    if isinstance(value, dict):
        return ""
    return _dump_properties_scalar(value)


def _dump_properties_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return str(value)
