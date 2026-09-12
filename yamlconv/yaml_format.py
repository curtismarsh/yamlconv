"""A parser and dumper for a practical subset of YAML.

Supports block mappings, block sequences, flow lists/maps ([a, b],
{a: b}), quoted and plain scalars, and comments. Does not support
anchors, aliases, multi-document streams, or block scalars (| and >).
That subset covers the vast majority of hand-written config files;
anything fancier should go through a real YAML library.
"""

from __future__ import annotations

from typing import Any


def parse_yaml(text: str) -> Any:
    """Parse a YAML subset into plain dict/list/scalar values. Pure function."""
    lines = _preprocess(text)
    if not lines:
        return None
    value, _ = _parse_block(lines, 0, lines[0][0])
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


def _preprocess(text: str) -> list[tuple[int, str]]:
    result = []
    for raw_line in text.splitlines():
        stripped = _strip_comment(raw_line)
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        result.append((indent, stripped.strip()))
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


def _parse_block(lines: list[tuple[int, str]], start: int, indent: int):
    if _is_seq_item(lines[start][1]):
        return _parse_sequence(lines, start, indent)
    return _parse_mapping(lines, start, indent)


def _parse_mapping(lines: list[tuple[int, str]], start: int, indent: int):
    result: dict[str, Any] = {}
    i = start
    while i < len(lines) and lines[i][0] == indent:
        content = lines[i][1]
        colon = _find_colon(content)
        if colon == -1:
            raise ValueError(f"expected 'key: value' at: {content!r}")
        key = _dequote(content[:colon].strip())
        rest = content[colon + 1 :].strip()
        if rest == "":
            if i + 1 < len(lines) and lines[i + 1][0] > indent:
                value, i = _parse_block(lines, i + 1, lines[i + 1][0])
            else:
                value = None
                i += 1
        else:
            value = _parse_scalar(rest)
            i += 1
        result[key] = value
    return result, i


def _parse_sequence(lines: list[tuple[int, str]], start: int, indent: int):
    items: list[Any] = []
    i = start
    while i < len(lines) and lines[i][0] == indent and _is_seq_item(lines[i][1]):
        content = lines[i][1]
        rest = content[1:].strip()
        if rest == "":
            if i + 1 < len(lines) and lines[i + 1][0] > indent:
                value, i = _parse_block(lines, i + 1, lines[i + 1][0])
            else:
                value = None
                i += 1
        elif _find_colon(rest) != -1:
            # "- key: value" starts a mapping; deeper-indented lines continue it.
            virtual_indent = indent + (len(content) - len(rest))
            virtual_lines = [(virtual_indent, rest)]
            j = i + 1
            while j < len(lines) and lines[j][0] > indent:
                virtual_lines.append(lines[j])
                j += 1
            value, _consumed = _parse_mapping(virtual_lines, 0, virtual_indent)
            i = j
        else:
            value = _parse_scalar(rest)
            i += 1
        items.append(value)
    return items, i


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


def _dump_value(data: Any, level: int) -> list[str]:
    pad = "  " * level
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
            else:
                lines.append(f"{pad}- {_dump_scalar(item)}")
    else:
        lines.append(f"{pad}{_dump_scalar(data)}")
    return lines
