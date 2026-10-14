# RGSS3 Compatibility Analyzer

`rgss3_analyzer.py` is a read-only static analyzer for **extracted RPG Maker VX Ace RGSS3 scripts**.

It is designed to support the `RPG Maker VX Ace Developer` skill by turning a script folder into a compatibility index before an agent proposes patches.

## What it detects

- classes/modules reopened by multiple scripts;
- methods defined by multiple scripts;
- common VX Ace alias patterns (`alias`, `alias_method`);
- likely destructive overrides when a later definition does not visibly preserve the previous method;
- `$imported["Key"] = ...` definitions;
- `$imported["Key"]` reads and load-order problems;
- duplicate `$imported` keys;
- constants assigned in multiple scripts;
- globals written by multiple scripts;
- selected `DataManager` save/load hooks;
- scripts that inspect note fields / note tags;
- `require` / `load` declarations;
- script order from filename order or an optional extracted `order.json`.

## What it deliberately does not do

It does **not** execute Ruby and it is not a complete Ruby parser. It will miss some behavior produced through:

- `eval`, `class_eval`, `module_eval`;
- `define_method` or other metaprogramming;
- dynamically generated alias/method names;
- native extensions;
- behavior hidden behind external runtime modifications.

A finding is a **review candidate**, not proof of incompatibility.

## Usage

```bash
python tools/rgss3_analyzer.py extracted-scripts/
```

Write both machine-readable and human-readable reports:

```bash
python tools/rgss3_analyzer.py extracted-scripts/ \
  --json analysis/script-compatibility.json \
  --markdown analysis/script-compatibility.md
```

If the extractor provides the actual Script Editor order:

```bash
python tools/rgss3_analyzer.py extracted-scripts/ \
  --order scripts/order.json \
  --json analysis/script-compatibility.json \
  --markdown analysis/script-compatibility.md
```

For CI or agent pipelines, fail when a high-severity method collision exists:

```bash
python tools/rgss3_analyzer.py extracted-scripts/ --fail-on-high
```

Exit code `2` means high-severity findings were present.

## Order file

The optional order file may be either an array:

```json
[
  "001_Core.rb",
  "002_Battle.rb",
  "003_Menu.rb"
]
```

or an object containing `scripts` / `order`:

```json
{
  "scripts": [
    {"path": "001_Core.rb"},
    {"path": "002_Battle.rb"}
  ]
}
```

Scripts not mentioned are appended in deterministic filename order.

## Severity model

### High

Usually means a high-risk lifecycle/battle/save method has multiple definitions and one or more later definitions do not visibly alias the prior implementation, or three or more competing implementations exist.

### Medium

Usually means a nontrivial duplicate method definition, a load-order-sensitive `$imported` dependency, or another candidate requiring manual review.

### Low

Typically means multiple method definitions exist but the later scripts visibly use the conventional VX Ace alias-and-redefine pattern.

Even a low-severity finding can still be incompatible if the scripts disagree about arguments, return values, state, or ordering.

## Tests

```bash
python -m unittest discover -s tests/tooling -v
```

The test fixtures are synthetic original code and do not contain RPG Maker default scripts.

## VX Ace Project Reader — v0.6

```bash
python tools/vxace_project_reader.py PATH_TO_PROJECT
```

The reader creates a separate normalized project index and automatically runs `rgss3_analyzer.py` after extracting `Scripts.rvdata2`.

Key properties:

- read-only source handling;
- source SHA-256 inventory;
- inert Marshal decoding through `rvdata2_bridge.rb`;
- no execution of extracted project scripts;
- normalized database/maps;
- Script Editor order preservation;
- switch/variable/event relationship indexes;
- symbolic ID-to-name resolution.

By default the output is a sibling of the source project (`ProjectName-project-index`). The reader refuses to emit generated files inside the source project.

### Current dependency

v0.6 requires an external Ruby executable for Marshal decoding. This is intentionally isolated behind the bridge so a future pure-Python backend can replace it without changing the project-index contract.

## Project Codex — v0.6

Generate the normalized project index and codex together:

```bash
python tools/vxace_project_reader.py PROJECT
```

Or regenerate only the codex:

```bash
python tools/vxace_codex.py PROJECT_INDEX
```

Codex output lives under `PROJECT_INDEX/codex/` and contains evidence-first system/state candidates, a relationship graph, map/event/page dependencies, and script-order/ownership/collision summaries.

Run all automated suites with:

```bash
python tools/run_tests.py
```
