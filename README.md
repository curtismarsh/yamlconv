# yamlconv

Converts between nested YAML config files and flat `key=value` properties
files.

Nested YAML is nice to hand-edit but bad for a lot of tooling: build
systems that only understand Java-style `.properties` files, `diff`
output that's noisy because a single value change reindents a whole
block, or scripts that want to inject one setting via an environment
variable. Flattening a `server.port: 8080` YAML entry into
`server.port=8080` fixes all three, and this tool converts either
direction so you're not stuck picking one format.

There is no dependency on PyYAML or any other third-party library. The
project implements its own parser for a practical subset of YAML
(mappings, sequences, flow lists/maps, quoted and plain scalars,
comments, literal/folded block scalars, and anchors/aliases) rather
than requiring one; merge keys (`<<:`) and multi-document streams are
not supported.

## Example

Given `config.yaml`:

```yaml
server:
  host: localhost
  port: 8080
debug: true
tags: [web, api]
```

```
$ python -m yamlconv.cli to-properties config.yaml
debug=true
server.host=localhost
server.port=8080
tags=web,api
```

And back:

```
$ python -m yamlconv.cli to-properties config.yaml -o config.properties
$ python -m yamlconv.cli to-yaml config.properties
debug: true
server:
  host: localhost
  port: 8080
tags:
  - web
  - api
```

Pass `-` as the input path to read from stdin, and `--sep` to change the
key separator used for flattened paths (default `.`).

## Library usage

Every conversion primitive is a pure function: no file I/O, no global
state, same input always gives the same output. That's what the CLI in
`yamlconv/cli.py` is built on top of, and it's why the whole thing is
easy to unit test (see `tests/test_convert.py`).

```python
from yamlconv import parse_yaml, flatten, dump_properties

data = parse_yaml(open("config.yaml").read())
flat = flatten(data)
print(dump_properties(flat))
```

## Current limitations

- Lists are treated as single leaf values by `flatten`/`unflatten`, not
  expanded into indexed keys. A list of scalars round-trips through the
  properties format as a comma-joined value; a list containing nested
  dicts round-trips through YAML but isn't addressable key-by-key.
- A comma inside a plain string value will be read back as a list when
  round-tripping through the properties format.
- Anchors (`&name`) and aliases (`*name`) are only recognized on
  block-level values (a mapping value or a sequence item), not inside
  flow collections like `[*name]`. Merge keys (`<<:`) aren't supported.
- No support for multi-document streams or explicit block scalar
  indentation indicators (e.g. `|2`).

## Development

Standard library only, no install step needed. Run the tests with:

```
python -m unittest discover tests
```
