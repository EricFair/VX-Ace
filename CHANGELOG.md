# Changelog

Each release keeps original projects read-only; every write happens on a new disposable copy behind exact native guards. Operation details and limits are in the linked references.

## 1.20.0 — Usable items, effects and features

- Database append gains usable items (template clone; key items stay with `append_key_item`) and bounded full-list overrides of skill/item **effects** and weapon/armor/state **features**, with editor-matching Integer/Float encodings. Every referenced States/Skills/CommonEvents/System file is bound by its own hash; recipes can point effects and features at a state or skill appended earlier. Verified in the real engine: a Hi-Potion healed 50% and cured a new state, an Ether restored 30 MP, and a Poison Dagger carried its attack state, attack element, hit bonus and element rate. See [database append](references/database-append.md).

## 1.19.0 — Branching event commands

- Staged event pages gain Show Choices with branches, Conditional Branch (switch, variable, self switch, gold, item) with else, Battle Processing with win/escape/lose branches, Change Party Member, Call Common Event, Change Gold/Items, Transfer Player and Wait; nesting up to 4 levels. Each referenced database and destination map is bound by its own hash; recipes can feed a new troop or key item into a battle or item check. Verified in the real engine: a choice recruit, a locked/open door and a boss battle lost into its lose branch. See [staged events](references/staged-events.md).

## 1.18.0 — Quest-stage events

- `append_staged_event` builds one event with 1..8 action-button pages (switch, variable and self-switch conditions), literal dialogue and Control Switches/Variables/Self Switch commands; recipe step `append_staged_event`. Verified in the real engine: three talks advanced a quest NPC through all pages. See [staged events](references/staged-events.md).

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
