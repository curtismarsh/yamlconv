import unittest

from yamlconv import (
    dump_yaml,
    flatten,
    parse_yaml,
    properties_to_yaml,
    unflatten,
    yaml_to_properties,
)


class FlattenUnflattenTests(unittest.TestCase):
    def test_round_trip_nested_scalars(self):
        data = {
            "server": {"host": "localhost", "port": 8080},
            "debug": True,
            "tags": ["a", "b"],
        }
        flat = flatten(data)
        self.assertEqual(
            flat,
            {
                "server.host": "localhost",
                "server.port": 8080,
                "debug": True,
                "tags": ["a", "b"],
            },
        )
        self.assertEqual(unflatten(flat), data)

    def test_custom_separator(self):
        data = {"a": {"b": {"c": 1}}}
        flat = flatten(data, sep="/")
        self.assertEqual(flat, {"a/b/c": 1})
        self.assertEqual(unflatten(flat, sep="/"), data)

    def test_empty_dict_round_trips(self):
        self.assertEqual(unflatten(flatten({})), {})


class YamlFormatTests(unittest.TestCase):
    def test_parse_simple_mapping(self):
        text = "name: demo\nport: 8080\ndebug: true\n"
        self.assertEqual(
            parse_yaml(text), {"name": "demo", "port": 8080, "debug": True}
        )

    def test_parse_nested_mapping_and_sequence(self):
        text = "server:\n  host: localhost\n  port: 8080\ntags:\n  - a\n  - b\n"
        self.assertEqual(
            parse_yaml(text),
            {"server": {"host": "localhost", "port": 8080}, "tags": ["a", "b"]},
        )

    def test_dump_then_parse_round_trip(self):
        data = {"a": 1, "b": {"c": "hello world", "d": [1, 2, 3]}, "e": None}
        self.assertEqual(parse_yaml(dump_yaml(data)), data)

    def test_flow_style_list(self):
        self.assertEqual(parse_yaml("tags: [web, api]\n"), {"tags": ["web", "api"]})


class ConversionPipelineTests(unittest.TestCase):
    def test_yaml_to_properties_and_back(self):
        yaml_text = "server:\n  host: localhost\n  port: 8080\n"
        properties_text = yaml_to_properties(yaml_text)
        self.assertEqual(
            properties_text, "server.host=localhost\nserver.port=8080\n"
        )
        self.assertEqual(
            properties_to_yaml(properties_text),
            "server:\n  host: localhost\n  port: 8080\n",
        )


if __name__ == "__main__":
    unittest.main()
