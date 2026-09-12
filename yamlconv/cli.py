"""Command-line entry point. This is the only module that does file I/O;
everything it calls into is pure and importable on its own.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .convert import properties_to_yaml, yaml_to_properties


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="yamlconv",
        description="Convert between nested YAML and flat properties-style config files.",
    )
    parser.add_argument("direction", choices=["to-properties", "to-yaml"])
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

    if args.direction == "to-properties":
        result = yaml_to_properties(text, sep=args.sep)
    else:
        result = properties_to_yaml(text, sep=args.sep)

    if args.output:
        Path(args.output).write_text(result)
    else:
        sys.stdout.write(result)


if __name__ == "__main__":
    main()
