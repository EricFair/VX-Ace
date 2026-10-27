# Notetag registry

Many VX Ace scripts read configuration from `<tag: value>` text in database notes, map notes and event comments. `tools/vxace_notetags.py` builds a read-only registry linking those notetag uses in a fresh Project Reader index to the scripts whose regexes appear to parse them. Use it to spot a misspelled tag, a tag no script reads, or two scripts competing for the same tag.

```powershell
python tools/vxace_notetags.py PROJECT_INDEX --project PROJECT --json NEW_REPORT.json --markdown NEW_REPORT.md
```

Both report paths must be new files outside the project and the index. The usual manifest, freshness and source-unchanged checks apply, and every walk is bounded; exceeding a budget refuses instead of returning a partial result. Exit codes: `0` ok, `2` refused, `3` review required (unrecognized tags or case mismatches were found).

## What it collects

- **Uses:** `note` fields of actors, classes, skills, items, weapons, armors, enemies, states and tilesets; map notes; and comment commands (108/408) in map, common and troop events. Forms read: `<tag>`, `<tag: value>`, `<tag arg arg>` and `</tag>`. Names are case-folded with whitespace collapsed; space and underscore are interchangeable when matching.
- **Parsers:** regex literals, `%r{}` and quoted strings in indexed scripts that look like notetag patterns, e.g. `/<foo[ _]bar:\s*(\d+)>/i` or `/<(?:FOO|BAR)>/i`. Candidate names come from the literal text after `<`; simple alternations are expanded and `[ _]`/`\s*` are treated as separators. Patterns that cannot be reduced to a literal prefix (interpolation, `<(\w+)>`) are listed as `opaque` with a reason.

## Classifications

- `recognized` / `unrecognized` per used tag, with up to three nearest-name suggestions for possible typos.
- `case_mismatches` when only parsers without `/i` match a tag and the written case differs.
- `possible_collisions` when parser patterns for the same tag appear in more than one script.
- `unused_parser_tags` (informational): parser tags that nothing in the project uses. Plugins often parse tags a game never needs.

## Limits

Every classification is a heuristic. Static regex inspection is evidence, not proof: scripts may build patterns dynamically, parse tags through helper methods, or alias another script's parser. An `unrecognized` tag may still be read by an opaque parser (the report counts them). Event comments are read line by line; multi-line literals, heredocs and trailing comments in scripts are not understood. No project code is ever evaluated.

The registry never authorizes edits. Fixing a tag, adding a note or changing a script still goes through the normal guarded copy-patch workflow with its own review.
