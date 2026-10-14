# Third-party provenance and license notice

The files in `rpgvxace_mcp/`, `UPSTREAM_README.md`, `UPSTREAM_pyproject.toml`, and `tests/marshal_codec/upstream_marshal.py` are copied without source modifications from:

- Repository: https://github.com/azureknight63/rpgvxace-mcp
- Revision: `75d7360fc12eda3046881e0424f136a9a5c01487`
- License: MIT, as explicitly declared in the retained upstream README and package metadata.

The original package paths for the three Python modules are `src/rpgvxace_mcp/{__init__,marshal_rb,rubytypes}.py`; the retained test is `tests/test_marshal.py`. `manifest.json` records original paths, destination paths, and SHA-256 hashes. Do not edit these pinned files directly: record any future divergence and keep upstream provenance.

Upstream supplies no separate LICENSE file or explicit copyright-holder line at this revision. All supplied source text and license declarations are retained. No affiliation, authorship of upstream code, or exclusive rights are claimed by this project.

MIT permission text (license identified by upstream):

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

Only inert Marshal data representations and codec code are included as runtime code. The upstream project writer, MCP server, backups, structural editing tools and raw-data write interface are deliberately absent from this dependency subset.
