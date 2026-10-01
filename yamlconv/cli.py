"""Command-line entry point. This is the only module that does file I/O;
everything it calls into is pure and importable on its own.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .convert import (
    json_to_properties,
    json_to_yaml,
    properties_to_json,
    properties_to_yaml,
    yaml_to_json,
    yaml_to_properties,
)

# Each converter takes (text, sep). The YAML-only targets ignore sep.
_CONVERTERS = {
    "to-properties": lambda text, sep: yaml_to_properties(text, sep=sep),
    "to-yaml": lambda text, sep: properties_to_yaml(text, sep=sep),
    "yaml-to-json": lambda text, sep: yaml_to_json(text),
    "properties-to-json": lambda text, sep: properties_to_json(text, sep=sep),
    "json-to-yaml": lambda text, sep: json_to_yaml(text),
    "json-to-properties": lambda text, sep: json_to_properties(text, sep=sep),
}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="yamlconv",
        description="Convert between nested YAML and flat properties-style config files.",
    )
    parser.add_argument("direction", choices=list(_CONVERTERS))
    parser.add_argument("input", help="path to input file, or - for stdin")
    parser.add_argument("-o", "--output", help="path to output file, defaults to stdout")
    parser.add_argument(
        "--sep",
        default=".",
        help="key separator used for flattened paths (default: '.')",
    )
    args = parser.parse_args(argv)

    if args.input == "-":
        text = sys.stdin.read()
    else:
        text = Path(args.input).read_text()

    try:
        result = _CONVERTERS[args.direction](text, args.sep)
    except ValueError as exc:
        parser.exit(1, f"yamlconv: {exc}\n")

    if args.output:
        Path(args.output).write_text(result)
    else:
        sys.stdout.write(result)


if __name__ == "__main__":
    main()
