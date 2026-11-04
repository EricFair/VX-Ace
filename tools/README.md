# VX Ace Developer tools

One line per tool. Every tool is evidence-first: reports go to a new directory outside the game, and writes go only to a disposable copy unless you use [adopt](../references/adopt.md) or an in-place recipe run on a project you designate as a working or test project ([recipes](../references/recipes.md)). Full commands, flags and limits are in [VXACE_MASTER.md](../VXACE_MASTER.md) and the linked references. Run any tool with `--help` for its options.

Guarded operations need the Python backend: pass `--backend python` (recipes and the master pass select it automatically). The RTP is auto-detected; `--rtp PATH` overrides it and `VXACE_NO_RTP_AUTODETECT=1` disables detection.

## Read-only analysis

- `vxace_master.py` — one-command validation and understanding workflow ([master](../VXACE_MASTER.md)).
- `vxace_project_validator.py` — byte round-trip check of every `Data/*.rvdata2` plus host Ruby syntax diagnostics ([validation](../references/project-validation.md)).
- `vxace_project_reader.py` — normalized index of database, maps and scripts, plus the Codex and overview ([reader](../references/project-reader.md)).
- `vxace_codex.py` — evidence-first Project Codex (quests, battle gates, cutscenes, common-event systems) ([codex](../references/project-codex.md)).
- `vxace_overview.py` — one-page `overview.md` / `overview.json`, written by the reader.
- `rgss3_analyzer.py` — static RGSS3 class, method, alias and load-order analysis ([compatibility index](../references/script-compatibility-index.md)).
- `vxace_inspect.py` — observed schema and reference lint.
- `vxace_schema_diff.py` — observed schema compared with a baseline project ([schema comparison](../references/schema-comparison.md)).
- `vxace_search.py`, `vxace_regex_search.py`, `vxace_index_query.py` — bounded literal and regex search over a fresh index ([search](../references/search-and-event-diagnostics.md), [regex](../references/regex-search.md)).
- `vxace_event_lint.py`, `vxace_common_event_graph.py` — event diagnostics and common-event call cycles ([cycles](../references/common-event-cycles.md)).
- `vxace_map_audit.py` — map tiles, passage flags, regions, shadows ([tile audit](../references/map-tile-audit.md)).
- `vxace_asset_audit.py`, `vxace_image_headers.py`, `vxace_rtp.py` — graphics/audio references, PNG headers, RTP detection ([asset audit](../references/asset-audit.md), [headers](../references/image-header-layouts.md)).
- `vxace_balance.py` — damage formulas, curves, matchups, economy and troop balance ([balance](../references/balance-analysis.md)).
- `vxace_notetags.py` — notetag registry against script parsers ([notetags](../references/notetag-registry.md)).
- `vxace_text_export.py`, `vxace_text_import.py` — text export/lint to CSV; import of the edited CSV as a patch spec ([export](../references/text-export.md), [import](../references/text-import.md)).
- `vxace_patch_planner.py`, `vxace_impact.py`, `vxace_index_diff.py`, `vxace_semantic_diff.py` — patch planning, dependency impact, and before/after diffs ([planning](../references/patch-planning.md), [impact](../references/impact-analysis.md)).
- `vxace_native_syntax.py`, `native_syntax_harness.rb` — compile-only native syntax diagnostics ([native syntax](../references/native-syntax-diagnostics.md)).
- `vxace_mcp.py`, `vxace_mcp_api.py` — optional read-only MCP adapter over stdio ([MCP](../references/mcp-read-only.md)).
- `vxace_codec_audit.py` — experimental Python codec audit; never grants mutation readiness.
- Snapshot helpers that capture exact native preconditions before an operation: `vxace_database_entries.py`, `vxace_maps.py`, `vxace_map_regions.py`, `vxace_map_names.py`, `vxace_map_labels.py`, `vxace_event_snapshot.py`, `vxace_character_graphics.py`, `vxace_system_fields.py`.

## Guarded operations (disposable copy, `--backend python`)

- `vxace_copy_patcher.py` — applies a reviewed patch spec to a new copy behind exact native gates ([copy mutation](../references/copy-mutation.md)).
- `vxace_event_structure.py` — command and page insertion and deletion ([event structure](../references/event-structure.md)).
- `vxace_database_append.py`, `vxace_database_edit.py`, `vxace_class_learning.py` — database appends, existing-entry edits and class learnings ([database append](../references/database-append.md)).
- `vxace_system_fields.py` — starting party, start position, title, currency, terms, switch and variable names ([system fields](../references/system-fields.md)).
- `vxace_map_regions.py`, `vxace_upper_tiles.py`, `vxace_map_layout.py` — region cells, upper-layer tiles, generated layouts ([regions](../references/map-region-editing.md), [tiles](../references/upper-tile-painting.md), [layouts](../references/map-layouts.md)).
- `vxace_map_events.py`, `vxace_staged_commands.py`, `vxace_event_rewards.py`, `vxace_map_shops.py`, `vxace_map_encounters.py`, `vxace_common_event_append.py` — new events, quest-stage pages, rewards, shops, encounters, common events ([staged events](../references/staged-events.md), [shops](../references/map-shops.md), [encounters](../references/map-encounters.md)).
- `vxace_maps.py`, `vxace_transfers.py` — blank/fresh map append and direct transfers ([blank map](../references/blank-map-append.md), [transfer](../references/direct-map-transfer.md)).
- `vxace_map_names.py`, `vxace_map_labels.py` — map display name and editor/tree name ([names](../references/map-display-names.md), [labels](../references/map-tree-names.md)).
- `vxace_script_slots.py` — one script slot before Main ([script slot](../references/script-slot-insertion.md)).

## Recipes, adopt and smoke

- `vxace_recipe.py` — `validate`, `plan` (read-only dry run with balance), `run` (copy chain, or `--in-place --confirm-in-place NAME`), and `undo` ([recipes](../references/recipes.md); examples in `tools/recipes/`).
- `vxace_recipe_plan.py`, `vxace_rtp_sprites.py` — recipe dry-run engine and the `{"sprite": ...}` graphic lookup ([RTP sprites](../references/rtp-sprites.md)).
- `vxace_adopt.py` — `plan`, `apply`, `status`, `undo`: bring a reviewed copy into the working project with a backup ([adopt](../references/adopt.md)).
- `vxace_smoke.py`, `smoke/` — in-engine smoke runs and one-line `check`s with screenshots; needs a visible, active game window ([smoke testing](../references/smoke-testing.md)).

## Codec and support

- `rvdata2_bridge.rb` — read-only Ruby Marshal bridge used for extraction.
- `rvdata2_mutator.rb`, `vxace_python_mutator.py` — Ruby and Python mutators behind the copy patcher; the Python one uses the pinned codec in `_vendor/` ([notice](_vendor/NOTICE.md)).
- `vxace_cache.py` — content-hash cache that speeds up recipe steps; failed gates are never cached.
- `vxace_codex_lib/` is the Codex implementation; `data/` holds catalogue data; `fixtures/` is sample input.
