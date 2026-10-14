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
