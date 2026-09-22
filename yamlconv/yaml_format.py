"""A parser and dumper for a practical subset of YAML.

Supports block mappings, block sequences, flow lists/maps ([a, b],
{a: b}), quoted and plain scalars, comments, literal/folded block
scalars (| and >, with -/+ chomping indicators), and anchors/aliases
(&name / *name) on block-level values. Does not support merge keys
(<<:), aliases inside flow collections, multi-document streams, or
explicit block scalar indentation indicators. That subset covers the
vast majority of hand-written config files; anything fancier should go
through a real YAML library.
"""

from __future__ import annotations

import copy
import re
from typing import Any


def parse_yaml(text: str) -> Any:
    """Parse a YAML subset into plain dict/list/scalar values. Pure function."""
    raw_lines = text.splitlines()
    lines = _preprocess(raw_lines)
    if not lines:
        return None
    anchors: dict[str, Any] = {}
    value, _ = _parse_block(lines, 0, lines[0][0], raw_lines, anchors)
    return value


def dump_yaml(data: Any) -> str:
    """Render a dict/list/scalar structure back into YAML text. Pure function."""
    if isinstance(data, dict) and not data:
        return "{}\n"
    if isinstance(data, list) and not data:
        return "[]\n"
    lines = _dump_value(data, 0)
    return "\n".join(lines) + "\n"


# ---- parsing --------------------------------------------------------------


def _preprocess(raw_lines: list[str]) -> list[tuple[int, str, int]]:
    """Strip comments and blank lines, keeping each entry's original line number.

    The line number lets block scalar consumption jump back into the raw,
    comment-preserving text once it hits a `|` or `>` indicator.
    """
    result = []
    for idx, raw_line in enumerate(raw_lines):
        stripped = _strip_comment(raw_line)
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        result.append((indent, stripped.strip(), idx))
    return result


def _strip_comment(line: str) -> str:
    in_single = in_double = False
    for i, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            if i == 0 or line[i - 1].isspace():
                return line[:i]
    return line


def _find_colon(content: str) -> int:
    in_single = in_double = False
    for i, ch in enumerate(content):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == ":" and not in_single and not in_double:
            if i + 1 == len(content) or content[i + 1] == " ":
                return i
    return -1


def _is_seq_item(content: str) -> bool:
    return content == "-" or content.startswith("- ")


_BLOCK_SCALAR_RE = re.compile(r"^([|>])([+-]?)$")
_ANCHOR_RE = re.compile(r"^&(\S+)(?:\s+(.*))?$")
_ALIAS_RE = re.compile(r"^\*(\S+)$")


def _block_scalar_style(rest: str) -> tuple[str, str] | None:
    match = _BLOCK_SCALAR_RE.match(rest)
    if not match:
        return None
    return match.group(1), match.group(2)


def _extract_anchor(rest: str) -> tuple[str | None, str]:
    """Split a leading `&name` off a value, returning (name, remainder).

    `remainder` is always a suffix of `rest` (only leading whitespace and
    the anchor token are removed), which matters for the virtual_indent
    math in _parse_sequence below.
    """
    match = _ANCHOR_RE.match(rest)
    if not match:
        return None, rest
    return match.group(1), (match.group(2) or "")


def _resolve_alias(anchors: dict[str, Any], name: str) -> Any:
    if name not in anchors:
        raise ValueError(f"undefined alias: *{name}")
    # Deep-copy so each alias use owns an independent structure; otherwise
    # mutating one occurrence would silently mutate every other occurrence.
    return copy.deepcopy(anchors[name])


def _parse_block(
    lines: list[tuple[int, str, int]],
    start: int,
    indent: int,
    raw_lines: list[str],
    anchors: dict[str, Any],
):
    if _is_seq_item(lines[start][1]):
        return _parse_sequence(lines, start, indent, raw_lines, anchors)
    return _parse_mapping(lines, start, indent, raw_lines, anchors)


def _parse_mapping(
    lines: list[tuple[int, str, int]],
    start: int,
    indent: int,
    raw_lines: list[str],
    anchors: dict[str, Any],
):
    result: dict[str, Any] = {}
    i = start
    while i < len(lines) and lines[i][0] == indent:
        content = lines[i][1]
        colon = _find_colon(content)
        if colon == -1:
            raise ValueError(f"expected 'key: value' at: {content!r}")
        key = _dequote(content[:colon].strip())
        rest = content[colon + 1 :].strip()
        anchor_name, rest = _extract_anchor(rest)
        style = _block_scalar_style(rest)
        if style is not None:
            value, i = _parse_block_scalar(raw_lines, lines, i, indent, style)
        elif rest == "":
            if i + 1 < len(lines) and lines[i + 1][0] > indent:
                value, i = _parse_block(lines, i + 1, lines[i + 1][0], raw_lines, anchors)
            else:
                value = None
                i += 1
        elif _ALIAS_RE.match(rest):
            value = _resolve_alias(anchors, _ALIAS_RE.match(rest).group(1))
            i += 1
        else:
            value = _parse_scalar(rest)
            i += 1
        if anchor_name is not None:
            anchors[anchor_name] = value
        result[key] = value
    return result, i


def _parse_sequence(
    lines: list[tuple[int, str, int]],
    start: int,
    indent: int,
    raw_lines: list[str],
    anchors: dict[str, Any],
):
    items: list[Any] = []
    i = start
    while i < len(lines) and lines[i][0] == indent and _is_seq_item(lines[i][1]):
        content = lines[i][1]
        rest = content[1:].strip()
        anchor_name, rest = _extract_anchor(rest)
        style = _block_scalar_style(rest)
        if style is not None:
            value, i = _parse_block_scalar(raw_lines, lines, i, indent, style)
        elif rest == "":
            if i + 1 < len(lines) and lines[i + 1][0] > indent:
                value, i = _parse_block(lines, i + 1, lines[i + 1][0], raw_lines, anchors)
            else:
                value = None
                i += 1
        elif _ALIAS_RE.match(rest):
            value = _resolve_alias(anchors, _ALIAS_RE.match(rest).group(1))
            i += 1
        elif _find_colon(rest) != -1:
            # "- key: value" starts a mapping; deeper-indented lines continue it.
            virtual_indent = indent + (len(content) - len(rest))
            virtual_lines = [(virtual_indent, rest, lines[i][2])]
            j = i + 1
            while j < len(lines) and lines[j][0] > indent:
                virtual_lines.append(lines[j])
                j += 1
            value, _consumed = _parse_mapping(
                virtual_lines, 0, virtual_indent, raw_lines, anchors
            )
            i = j
        else:
            value = _parse_scalar(rest)
            i += 1
        if anchor_name is not None:
            anchors[anchor_name] = value
        items.append(value)
    return items, i


def _parse_block_scalar(
    raw_lines: list[str],
    lines: list[tuple[int, str, int]],
    i: int,
    parent_indent: int,
    style: tuple[str, str],
):
    """Consume a `|`/`>` block scalar starting after `lines[i]`.

    Block scalar bodies are read straight from the raw source lines rather
    than the comment-stripped, blank-line-skipped `lines` list, since a `#`
    or a blank line inside the block is content, not syntax. Once the body
    is collected we skip `lines` forward past whatever raw lines it covered.
    """
    char, chomp = style
    start_raw_idx = lines[i][2]
    n = len(raw_lines)
    j = start_raw_idx + 1
    block_indent: int | None = None
    content_lines: list[str] = []
    last_raw_idx = start_raw_idx
    while j < n:
        raw = raw_lines[j]
        if raw.strip() == "":
            content_lines.append("")
            last_raw_idx = j
            j += 1
            continue
        cur_indent = len(raw) - len(raw.lstrip(" "))
        if block_indent is None:
            if cur_indent <= parent_indent:
                break
            block_indent = cur_indent
        if cur_indent < block_indent:
            break
        content_lines.append(raw[block_indent:])
        last_raw_idx = j
        j += 1

    trailing_blanks = 0
    while content_lines and content_lines[-1] == "":
        content_lines.pop()
        trailing_blanks += 1

    body = "\n".join(content_lines) if char == "|" else _fold_lines(content_lines)

    if not content_lines and not trailing_blanks:
        value = ""
    elif chomp == "-":
        value = body
    elif chomp == "+":
        value = body + "\n" * (trailing_blanks + 1)
    else:
        value = body + "\n"

    next_i = i + 1
    while next_i < len(lines) and lines[next_i][2] <= last_raw_idx:
        next_i += 1
    return value, next_i


def _fold_lines(lines: list[str]) -> str:
    if not lines:
        return ""
    parts: list[str] = [lines[0]]
    blank_run = 0
    for line in lines[1:]:
        if line == "":
            blank_run += 1
            continue
        if blank_run:
            parts.append("\n" * blank_run)
            blank_run = 0
        else:
            parts.append(" ")
        parts.append(line)
    if blank_run:
        parts.append("\n" * blank_run)
    return "".join(parts)


def _split_flow(inner: str) -> list[str]:
    parts = []
    depth = 0
    in_single = in_double = False
    current: list[str] = []
    for ch in inner:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch in "[{" and not in_single and not in_double:
            depth += 1
        elif ch in "]}" and not in_single and not in_double:
            depth -= 1
        if ch == "," and depth == 0 and not in_single and not in_double:
            parts.append("".join(current))
            current = []
            continue
        current.append(ch)
    if current or parts:
        parts.append("".join(current))
    return parts


def _dequote(s: str) -> str:
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        inner = s[1:-1]
        if s[0] == '"':
            return inner.replace('\\"', '"').replace("\\\\", "\\")
        return inner.replace("''", "'")
    return s


def _parse_scalar(s: str) -> Any:
    s = s.strip()
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part.strip()) for part in _split_flow(inner)]
    if s.startswith("{") and s.endswith("}"):
        inner = s[1:-1].strip()
        if not inner:
            return {}
        result = {}
        for part in _split_flow(inner):
            key, _sep, value = part.partition(":")
            result[_dequote(key.strip())] = _parse_scalar(value.strip())
        return result
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return _dequote(s)
    if s in ("null", "Null", "NULL", "~", ""):
        return None
    if s in ("true", "True", "TRUE"):
        return True
    if s in ("false", "False", "FALSE"):
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


# ---- dumping ----------------------------------------------------------------


def _looks_numeric(s: str) -> bool:
    try:
        int(s)
        return True
    except ValueError:
        pass
    try:
        float(s)
        return True
    except ValueError:
        return False


def _dump_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return _dump_string(value)
    raise TypeError(f"cannot dump value of type {type(value).__name__}")


def _dump_string(s: str) -> str:
    if s == "":
        return "''"
    needs_quote = s.strip() != s
    if s.lower() in ("true", "false", "null", "~", "yes", "no"):
        needs_quote = True
    if _looks_numeric(s):
        needs_quote = True
    if s[0] in "-?" and (len(s) == 1 or s[1] == " "):
        needs_quote = True
    if any(ch in s for ch in ":#[]{},&*!|>'\"%@`"):
        needs_quote = True
    if needs_quote:
        escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return s


def _dump_block_scalar(value: str, pad: str) -> list[str]:
    """Render a multi-line string as a literal (`|`) block scalar.

    A raw newline can't survive inside a quoted flow scalar, so any string
    containing "\\n" is written as a block instead of going through
    _dump_string.
    """
    if value.endswith("\n"):
        stripped = value.rstrip("\n")
        trailing = len(value) - len(stripped)
        if trailing > 1:
            indicator = "+"
            body_lines = stripped.split("\n") + [""] * (trailing - 1)
        else:
            indicator = ""
            body_lines = stripped.split("\n")
    else:
        indicator = "-"
        body_lines = value.split("\n")
    header = f"|{indicator}"
    content = [f"{pad}{line}" if line else "" for line in body_lines]
    return [header, *content]


def _dump_value(data: Any, level: int) -> list[str]:
    pad = "  " * level
    child_pad = "  " * (level + 1)
    lines: list[str] = []
    if isinstance(data, dict):
        for key, value in data.items():
            key_str = _dump_string(str(key))
            if isinstance(value, dict) and value:
                lines.append(f"{pad}{key_str}:")
                lines.extend(_dump_value(value, level + 1))
            elif isinstance(value, list) and value:
                lines.append(f"{pad}{key_str}:")
                lines.extend(_dump_value(value, level + 1))
            elif isinstance(value, dict):
                lines.append(f"{pad}{key_str}: {{}}")
            elif isinstance(value, list):
                lines.append(f"{pad}{key_str}: []")
            elif isinstance(value, str) and "\n" in value:
                header, *body = _dump_block_scalar(value, child_pad)
                lines.append(f"{pad}{key_str}: {header}")
                lines.extend(body)
            else:
                lines.append(f"{pad}{key_str}: {_dump_scalar(value)}")
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)) and item:
                sub_lines = _dump_value(item, level + 1)
                lines.append(f"{pad}- {sub_lines[0].strip()}")
                lines.extend(sub_lines[1:])
            elif isinstance(item, dict):
                lines.append(f"{pad}- {{}}")
            elif isinstance(item, list):
                lines.append(f"{pad}- []")
            elif isinstance(item, str) and "\n" in item:
                header, *body = _dump_block_scalar(item, child_pad)
                lines.append(f"{pad}- {header}")
                lines.extend(body)
            else:
                lines.append(f"{pad}- {_dump_scalar(item)}")
    else:
        lines.append(f"{pad}{_dump_scalar(data)}")
    return lines
