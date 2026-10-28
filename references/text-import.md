# Player-text import — v1.10

`tools/vxace_text_import.py` turns an edited [text-export](text-export.md) CSV into a reviewed **patch spec** that uses only change kinds the copy patcher already guards. It adds no mutation backend and is read-only: it reads a fresh Project Reader index and the CSV, and writes only the spec file(s) and a report outside the project and index. Nothing is applied until you run the normal planner and copy patcher.

## Workflow

1. Export: `vxace_text_export.py PROJECT_INDEX --project PROJECT --csv NEW\text.csv` (add `--include-name-commands` if you want actor names/nicknames/profiles).
2. Edit the `translation` column in Excel or any CSV editor. Leave it empty for rows you do not want to change. Do not edit `key` or `fingerprint`.
3. Import:

```powershell
python tools/vxace_text_import.py PROJECT_INDEX --project PROJECT --csv EDITED.csv `
  --spec-out NEW\spec.json --report NEW\import.md [--json NEW\import.json] [--allow-shorter] `
  [--max-width 50] [--max-width-face 38] [--max-lines 4] [--icon-count N]
```

4. Read the report, then plan, review impact and stage a disposable copy as usual:

```powershell
python tools/vxace_patch_planner.py PROJECT_INDEX --project PROJECT --spec NEW\spec.json --output NEW\plan
python tools/vxace_copy_patcher.py PROJECT_INDEX --project PROJECT --spec NEW\spec.json --copy NEW\copy --audit NEW\audit --backend python
```

5. Open the copy in the editor and do a smoke run (see [in-engine smoke tests](smoke-testing.md)) before replacing anything.

Outputs must be new files outside the project and the index. A stale index, a changed source, a malformed CSV or an existing output refuses with exit code 2 and writes nothing.

## Row statuses

| status | meaning |
|---|---|
| `applied` | produced one or more guarded changes |
| `unchanged` | translation equals the original (or no line differs) |
| `skipped_empty` | `translation` was empty |
| `stale` | the fingerprint in the CSV no longer matches the block in the fresh index (source edited since the export) |
| `unknown` | key not present in the fresh index |
| `duplicate` | the key appears more than once in the CSV; none of those rows are applied |
| `refused_line_count` | line/choice count does not match (see below) |
| `refused_invalid` | control characters, a multi-line value where one line is required, or an invalid display name |
| `unsupported` | no existing guarded operation can address it (for example System terms) |

Every non-applied row (except empty ones) is listed in the report with its reason. Lint warnings and padding notes for applied rows are listed too.

## Change kinds emitted

- **Event text** (map, common event and troop pages): `kind: event`, `mutation.action: set_parameter`, `parameter_index` 0 on the individual `401`/`405` line command, `locator` = `{map_id, event_id, page, command_index}`, `{common_event_id, command_index}` or `{troop_id, page, command_index}`. One change per changed line. The `101`/`105` header is never touched.
- **Choices (102)**: one `set_parameter` of parameter 0 with the full new choice array, plus one `set_parameter` of parameter 1 on each matching `402` branch label so the editor display stays consistent. Write the translation either one choice per line (as exported) or joined with ` | `.
- **Name commands** (`320/324/325`, only if exported): `set_parameter` of parameter 1.
- **Database text** (`db:TABLE/ID/FIELD`): `kind: database`, `locator {table, id}`, `mutation {field, value}`. The copy patcher requires the field to exist already and to be a string. Only `description` and `profile` accept newlines.
- **Map display name** (`map:NNN/display_name`): `kind: map_name`. This operation must be the only change in its transaction and needs a native map hash, so each display name is written to its own spec `NAME.mapname-001.json`, `-002`, ... next to the main spec. Run each separately; because each stages a new copy, apply them one at a time and re-index/re-import between steps if you chain them.

The main spec has no per-transaction size limit in the existing tools, so it is never split. If no ordinary change exists, the main spec file is not written.

## Line-count rule

A message (`101`+`401`) or scrolling text (`105`+`405`) translation is split on newlines and must have **exactly** as many lines as the original. Fewer lines are refused unless `--allow-shorter`, which pads with empty lines (reported). More lines are refused: adding lines means inserting commands, which is out of scope here. Choice counts must always match.

## Validation

- Control characters other than newline (including tab) are refused. CRLF/CR from Excel is normalised to newline. Excel-style quoting and a UTF-8 BOM are accepted.
- VX Ace escape codes (`\C[n]`, `\V[n]`, `\N[n]`, `\{` ...) are kept literally.
- Each new line goes through the export lint (width, line count, malformed/unknown codes, out-of-range references, whitespace). Findings are warnings, never refusals.

## Limits

- Heuristic lint only; no font metrics, no custom message systems.
- System database text (game title, currency, terms, type names) is `unsupported`: the guarded database edit addresses id-based rows only.
- Script-generated or plugin text, picture text, notes and command insertion/deletion are out of scope.
- Staleness is checked twice: the CSV fingerprint against the fresh index here, and the copy patcher's own source and round-trip gates afterwards. Always review in the editor and run the game before adopting a copy.

## Native evidence (v1.10)

On an editor-created project, an exported CSV with two edited cells (a map Show Text line and actor 1's nickname) produced a two-change spec; the planner and Python copy patcher applied it with all postgates. A [smoke run](smoke-testing.md) of the copy confirmed both values in the loaded data, started the event and found the imported line in the live message window. Editor display was not inspected in this run.
