# Changelog

Each release keeps original projects read-only; every write happens on a new disposable copy behind exact native guards. Operation details and limits are in the linked references.

## 1.17.0 — Adopt and daily workflow

- `vxace_adopt.py plan/apply/undo/status` brings a reviewed staged copy (single audit or recipe) into the working project: drift, undeclared-difference and smoke-harness refusals, editor/game-running refusal, per-file backup, atomic writes with rollback, verified undo. Verified on a stand-in project: recipe → plan → apply → real-engine smoke run → byte-identical undo. See [adopt](references/adopt.md).
- New [daily game development](workflows/daily-game-dev.md) guide and a rewritten [getting started](GETTING_STARTED.md) with Claude Code and Codex installs; SKILL.md boundary 8 now names adopt as its only exception.

## 1.16.1 — Clean skill repository

- Repository now contains only the skill: development tests, CI and historical validation records are kept out of the published tree. No tool or behaviour changes.

## 1.16.0 — Blank events from a schema donor

- `append_blank_event` creates a blank one-page event using an existing event only as a structural template; recipe step `append_blank_event`. See [map event creation](references/map-event-creation.md).

## 1.15.0 — Map shops

- `add_shop` inserts Shop Processing with existing goods into a blank or single-dialogue event; recipe steps `append_dialogue_event`, `add_shop`. See [map shops](references/map-shops.md).

## 1.14.0 — Class skill learnings

- `append_class_learning` adds one skill learning to a class; recipe step `append_learning`. See [database append](references/database-append.md).

## 1.13.0 — Recipes

- `vxace_recipe.py` chains guarded operations as separate transactions with `from_step` references and an optional smoke run. See [recipes](references/recipes.md).

## 1.12.0 — Map encounters

- `append_encounter` adds one random-encounter entry to a map. See [map encounters](references/map-encounters.md).

## 1.11.0 — Troops

- Troop append from a blank template troop with 1..8 existing enemies. See [database append](references/database-append.md).

## 1.10.0 — Text import

- `vxace_text_import.py` turns an edited text-export CSV into a spec of existing guarded edits. See [text import](references/text-import.md).

## 1.9.0 — Database appends

- Template-clone appends for enemies, skills, states, weapons and armors with whitelisted overrides; [release checklist](workflows/release-checklist.md). See [database append](references/database-append.md).

## 1.8.0 — In-engine smoke tests

- `vxace_smoke.py` stages a harness in a disposable copy and runs the real `Game.exe`. See [smoke testing](references/smoke-testing.md).

## 1.7.0 — Game-development analysis

- Read-only [balance](references/balance-analysis.md), [notetag](references/notetag-registry.md) and [text export](references/text-export.md) tools; new [patterns](patterns/README.md) and [RGSS3 templates](templates/rgss3/README.md); task-routed `SKILL.md`.

## 1.0.0 – 1.6.0 — Validated specialist and guarded authoring subset

- 1.0 validated specialist with one-time event rewards; 1.1 regex search; 1.2 blank-map append; 1.3 schema comparison; 1.4 direct map transfer (1.4.1 passage-order fix); 1.5 map display names; 1.6 editor/tree map names.

## 0.1 – 0.27 — Foundations

- Engine knowledge, patterns and compatibility analysis (0.1–0.4); project reader, Codex, planning and verified copy mutation (0.5–0.8); project validator, impact analysis and semantic diff (0.9–0.10); Python backend, structural event edits, search, diagnostics and audits (0.11–0.18); regions, key items, script fidelity, native syntax, script slots, upper tiles, dialogue events and character graphics (0.19–0.27).
