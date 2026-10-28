# Player-text export and lint — v1.7

`tools/vxace_text_export.py` exports the player-facing text of a project for proofreading or localization and runs a heuristic lint over it. It is read-only: it reads a fresh Project Reader index, never executes project code, and writes only new report files outside the project and index. No import or write-back is enabled.

```powershell
python tools/vxace_text_export.py PROJECT_INDEX --project PROJECT `
  --json NEW\text.json --csv NEW\text.csv --markdown NEW\script.md `
  [--include-name-commands] [--max-width 50] [--max-width-face 38] [--max-lines 4] [--icon-count N] [--max-findings 2000]
```

At least one output is required. Outputs must be new files, distinct, and outside both the source project and the index. A stale index, a source change during export, an opaque command or an exceeded budget refuses with exit code 2 and writes nothing; success is exit code 0.

## What is exported

- Event text from map, common and troop event pages: Show Text (`101` header with face name/index, background and position, plus its `401` lines as one block), Show Choices (`102` choices, cancel type, `402` branch labels), Show Scrolling Text (`105` + `405`). `--include-name-commands` adds Change Name/Nickname/Profile (`320/324/325`).
- Database text: names, nicknames, descriptions and profiles; skill messages (`message1/2`); state messages (`message1..4`); System game title, currency unit, element/skill/weapon/armor type names and terms (basic, params, etypes, commands); map display names. Empty strings are skipped.

Every entry has a stable key (for example `map:001/event:3/page:1/cmd:12`, `common:5/cmd:0`, `troop:2/page:1/cmd:4`, `db:states/1/message1`, `map:001/display_name`), the index file and evidence path, and a sha256 `fingerprint` of the exact source parameters (command code, indent and parameters; for database text the file, path and value). A future import could use it to confirm the source is unchanged.

## Formats

- `--json`: everything — entries, per-entry word counts, lint report, limits and freshness flags.
- `--csv`: `key, context, speaker, original, translation, fingerprint`; the translation column is empty. UTF-8 with BOM so Excel reads it correctly. Embedded newlines are quoted. Cells that begin with `=`, `+`, `-` or `@` are written as is, so treat the file as data, not trusted input to a spreadsheet macro.
- `--markdown`: a readable script grouped by map, event and page (then common events, troops and database), with word counts per group.

## Lint

Findings are labelled heuristic and counted per map (`map:NNN`, `common_events`, `troops`, `database`). Codes: `too_many_lines` (more than 4 lines), `line_too_wide` (visible width over 50, or 38 when the block has a face), `unknown_control_code`, `malformed_control_code`, `reference_out_of_range` (`\V[n]` outside the System variable list, `\N[n]` outside the actor list), `color_out_of_range` (`\C[n]` above 31), `empty_message`, `trailing_whitespace`, `doubled_space`, `malformed_parameters`. Leading indentation is not a doubled space. Counts are complete; the listed findings are capped by `--max-findings` and truncation is explicit.

Width, line-count and empty checks apply to Show Text; control-code and whitespace checks apply to all exported text.

## Limits

- Width counts visible characters with East Asian wide characters as 2; `\V \N \G \I` substitutions count as 0. Real font metrics and `\{ \}` size changes are not modelled, so a flagged line may fit and an unflagged one may not.
- Message-pack scripts add codes, wider windows and auto-wrap; those produce false positives. Tune the width options.
- `\I[n]` is an icon index, not a database id. It is range-checked only when `--icon-count` is given. `\P[n]` is not range-checked.
- Range checks are skipped when the index lacks the System or Actors table.
- Word counts split on whitespace and are not meaningful for languages without spaces.
- Script-generated text, plugin-drawn text, picture text and notes are not exported.
