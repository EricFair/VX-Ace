# Workflow — RGSS3 Compatibility Scan

Use this before modifying a project with multiple custom scripts.

## 1. Preserve source order

Extract scripts using their actual VX Ace Script Editor order. Do not alphabetize scripts if an authoritative order exists.

## 2. Run the analyzer

```bash
python tools/rgss3_analyzer.py scripts/ \
  --order scripts/order.json \
  --json analysis/script-compatibility.json \
  --markdown analysis/script-compatibility.md
```

## 3. Triage high-severity findings

For every high-severity method collision:

- inspect the earlier definition;
- inspect every later definition;
- inspect aliases in those scripts;
- determine the intended call chain;
- identify whether a full replacement intentionally supersedes another framework;
- check documented script order.

Do not "fix" a collision merely because it is flagged.

## 4. Review dependencies

For `$imported` findings:

- missing definition -> dependency may be absent or key may be set dynamically;
- defined later -> likely load-order problem unless deliberately deferred;
- duplicate key -> inspect whether two scripts claim the same identity.

## 5. Review save hooks

If multiple scripts touch `DataManager` save/load methods, verify each one preserves prior contents/behavior. Test:

- new game;
- save;
- load;
- old save where relevant;
- save after loading an old save.

## 6. Review note parsers

When multiple scripts parse notes:

- identify their tags/regexes;
- look for overlapping syntax;
- verify cache/initialization order;
- confirm database objects are parsed exactly once when expected.

## 7. Patch minimally

Prefer:

- an existing documented extension point;
- an alias/wrapper that preserves the established chain;
- a compatibility shim loaded after the involved scripts;
- configuration changes over invasive rewrites.

## 8. Re-run analysis

The post-patch report becomes part of the change record.

## 9. Test in the actual VX Ace runtime

Static analysis is necessary but not sufficient. Exercise the exact scene/battle/map/save paths touched by the collision.
