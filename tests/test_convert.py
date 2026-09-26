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

    def test_list_of_dicts_expands_into_indexed_keys(self):
        data = {"servers": [{"name": "a", "port": 1}, {"name": "b", "port": 2}]}
        flat = flatten(data)
        self.assertEqual(
            flat,
            {
                "servers.0.name": "a",
                "servers.0.port": 1,
                "servers.1.name": "b",
                "servers.1.port": 2,
            },
        )
        self.assertEqual(unflatten(flat), data)

    def test_list_of_scalars_stays_a_single_leaf(self):
        data = {"tags": ["a", "b"]}
        flat = flatten(data)
        self.assertEqual(flat, {"tags": ["a", "b"]})
        self.assertEqual(unflatten(flat), data)

    def test_nested_list_of_lists_expands_into_indexed_keys(self):
        data = {"matrix": [[1, 2], [3, 4]]}
        flat = flatten(data)
        self.assertEqual(
            flat, {"matrix.0": [1, 2], "matrix.1": [3, 4]}
        )
        self.assertEqual(unflatten(flat), data)

    def test_single_element_list_of_dicts_round_trips(self):
        data = {"servers": [{"name": "only"}]}
        self.assertEqual(unflatten(flatten(data)), data)


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


class BlockScalarTests(unittest.TestCase):
    def test_literal_block_scalar_default_chomping(self):
        text = "message: |\n  line one\n  line two\n"
        self.assertEqual(parse_yaml(text), {"message": "line one\nline two\n"})

    def test_literal_block_scalar_strip_chomping(self):
        text = "message: |-\n  line one\n  line two\nafter: 1\n"
        self.assertEqual(
            parse_yaml(text), {"message": "line one\nline two", "after": 1}
        )

    def test_literal_block_scalar_keep_chomping(self):
        text = "message: |+\n  line one\n\n\nafter: value\n"
        self.assertEqual(
            parse_yaml(text), {"message": "line one\n\n\n", "after": "value"}
        )

    def test_folded_block_scalar(self):
        text = "message: >\n  line one\n  line two\n"
        self.assertEqual(parse_yaml(text), {"message": "line one line two\n"})

    def test_block_scalar_in_sequence(self):
        text = "items:\n  - |\n    a\n    b\n  - plain\n"
        self.assertEqual(parse_yaml(text), {"items": ["a\nb\n", "plain"]})

    def test_block_scalar_ignores_hash_as_content(self):
        text = "message: |\n  keep # this\n"
        self.assertEqual(parse_yaml(text), {"message": "keep # this\n"})

    def test_dump_multiline_string_round_trips_with_trailing_newline(self):
        data = {"description": "first line\nsecond line\n"}
        dumped = dump_yaml(data)
        self.assertEqual(
            dumped, "description: |\n  first line\n  second line\n"
        )
        self.assertEqual(parse_yaml(dumped), data)

    def test_dump_multiline_string_round_trips_without_trailing_newline(self):
        data = {"note": "abc\ndef"}
        dumped = dump_yaml(data)
        self.assertEqual(dumped, "note: |-\n  abc\n  def\n")
        self.assertEqual(parse_yaml(dumped), data)


class AnchorAliasTests(unittest.TestCase):
    def test_scalar_anchor_and_alias(self):
        text = "base: &b hello\nother: *b\n"
        self.assertEqual(parse_yaml(text), {"base": "hello", "other": "hello"})

    def test_mapping_anchor_and_alias(self):
        text = (
            "defaults: &defaults\n"
            "  timeout: 30\n"
            "  retries: 3\n"
            "service: *defaults\n"
        )
        expected = {
            "defaults": {"timeout": 30, "retries": 3},
            "service": {"timeout": 30, "retries": 3},
        }
        self.assertEqual(parse_yaml(text), expected)

    def test_alias_is_independent_copy(self):
        text = "defaults: &defaults\n  timeout: 30\nservice: *defaults\n"
        data = parse_yaml(text)
        self.assertIsNot(data["defaults"], data["service"])
        data["service"]["timeout"] = 99
        self.assertEqual(data["defaults"]["timeout"], 30)

    def test_sequence_anchor_and_alias(self):
        text = "items:\n  - &first a\n  - *first\n  - b\n"
        self.assertEqual(parse_yaml(text), {"items": ["a", "a", "b"]})

    def test_undefined_alias_raises(self):
        with self.assertRaises(ValueError):
            parse_yaml("a: *missing\n")


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

    def test_yaml_to_properties_and_back_with_list_of_dicts(self):
        yaml_text = (
            "servers:\n"
            "  - name: a\n"
            "    port: 1\n"
            "  - name: b\n"
            "    port: 2\n"
        )
        properties_text = yaml_to_properties(yaml_text)
        self.assertEqual(
            properties_text,
            "servers.0.name=a\n"
            "servers.0.port=1\n"
            "servers.1.name=b\n"
            "servers.1.port=2\n",
        )
        self.assertEqual(properties_to_yaml(properties_text), yaml_text)


if __name__ == "__main__":
    unittest.main()
