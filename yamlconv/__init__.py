"""yamlconv: convert between nested YAML and flat properties-style config."""

from .yaml_format import parse_yaml, dump_yaml
from .convert import (
    flatten,
    unflatten,
    parse_properties,
    dump_properties,
    yaml_to_properties,
    properties_to_yaml,
    yaml_to_json,
    properties_to_json,
    json_to_yaml,
    json_to_properties,
)

__all__ = [
    "yaml_to_json",
    "properties_to_json",
    "json_to_yaml",
    "json_to_properties",
    "parse_yaml",
    "dump_yaml",
    "flatten",
    "unflatten",
    "parse_properties",
    "dump_properties",
    "yaml_to_properties",
    "properties_to_yaml",
]

__version__ = "0.1.0"
