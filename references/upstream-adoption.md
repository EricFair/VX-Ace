# Vendored Python codec — provenance

The Python Marshal codec behind the `--backend python` option is vendored from [azureknight63/rpgvxace-mcp](https://github.com/azureknight63/rpgvxace-mcp), pinned to commit `75d7360fc12eda3046881e0424f136a9a5c01487`. The license is MIT; see `tools/_vendor/NOTICE.md`.

## What is vendored

Only `marshal_rb.py`, `rubytypes.py` and package metadata are used. The upstream MCP server and game writer are not imported. Every vendored file is pinned by SHA-256 in `tools/_vendor/manifest.json`.

## How it is used

- It is the Python backend for reading and writing `.rvdata2` data. Guarded operations require it (`--backend python`); recipes and the master pass select it automatically.
- Every write still passes this toolkit's own gates: exact no-op byte round-trip, schema checks, fresh evidence, a disposable copy and re-indexing. The codec never grants permission by itself.
- `tools/vxace_codec_audit.py` runs an experimental read-only decode/encode comparison of a project's `Data/*.rvdata2` files and reports to a new external directory. A pass does not authorize mutation.
