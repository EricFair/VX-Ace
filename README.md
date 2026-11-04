# RPG Maker VX Ace Developer — v2.0

A skill and local toolchain that lets an AI agent work on **RPG Maker VX Ace** projects like a careful senior developer: analyse a project, design mechanics natively, build content (maps, events, monsters, shops, database entries) with guarded recipes, check it in the real engine and bring reviewed changes into your project with a backup and undo. Runtime code targets **RGSS3 / Ruby 1.9.2**.

- **Install and first session:** [GETTING_STARTED.md](GETTING_STARTED.md)
- **Agent entry point:** [SKILL.md](SKILL.md)
- **Every command, setting and safety rule:** [VXACE_MASTER.md](VXACE_MASTER.md) (machine-readable defaults in `vxace-master.json`)
- **Release history:** [CHANGELOG.md](CHANGELOG.md)

## What it does

| Area | Highlights | Reference |
|---|---|---|
| Understand a project | validator (byte-identical round trip of every data file), reader and Codex, one-page overview, script compatibility, asset/RTP and map-tile audits, search | [project reader](references/project-reader.md), [validation](references/project-validation.md) |
| Analyse | balance (formulas, curves, troops vs the party with equipment and hit rates, economy), notetag registry, text export and message lint, patch impact, semantic diff | [balance](references/balance-analysis.md), [impact](references/impact-analysis.md) |
| Build content | recipes: one JSON file of steps with `{"from_step": k}` links, a dry-run `plan` (ids, warnings, troop balance) and `run`; macros for monsters, areas with doors, shopkeepers, inns, intros, chests, touch triggers; readable map layouts; RTP sprite catalogue | [recipes](references/recipes.md) |
| Edit the database | append actors, classes, enemies, skills, states, weapons, armors, items, troops and skill learnings from templates; edit existing entries (`set_fields`, single feature rows); System fields | [database append](references/database-append.md), [system fields](references/system-fields.md) |
| Events | quest NPCs with conditional pages, choices, battles, shops, Recover All, movement and touch/parallel triggers; common events | [staged events](references/staged-events.md), [monsters](references/monsters.md) |
| Test in the engine | one-line `vxace_smoke.py check` (start map, expected events, steps, talk, auto-battle, in-engine screenshots), scripted suites, crash capture | [smoke testing](references/smoke-testing.md) |
| Design knowledge | native-first patterns (quests, crafting, day/night, puzzles, bosses) and RGSS3 templates | [patterns](patterns/README.md), [templates](templates/rgss3/README.md) |

Anything outside the enabled operations, such as autotile painting, event deletion or free-form map property edits, is refused. [SKILL.md](SKILL.md) lists the exact operations.

## A recipe in one minute

```json
{"title": "Cave slice", "steps": [
 {"type": "add_area", "template_map_id": 1, "name": "Cave", "width": 21, "height": 15, "tileset_id": 4, "layout": {"preset": "dungeon", "paths": [[10, 3]]}, "donor_event": 1, "door": {"map_id": 1, "x": 8, "y": 4, "blank_x": 1, "blank_y": 1}, "arrival": {"x": 10, "y": 12, "direction": 8}, "return_door": {"x": 10, "y": 13}, "back_to": {"x": 8, "y": 5, "direction": 2}},
 {"type": "append_entry", "table": "enemies", "template_id": 1, "overrides": {"name": "Cave Rat", "params": [60, 0, 12, 8, 5, 5, 10, 10]}},
 {"type": "append_entry", "table": "troops", "template_id": 1, "overrides": {"name": "Rats", "members": [{"enemy_id": {"from_step": 2}, "x": 200, "y": 300, "hidden": false}, {"enemy_id": {"from_step": 2}, "x": 340, "y": 300, "hidden": false}]}},
 {"type": "append_blank_event", "map_id": {"from_step": 1}, "donor_map_id": 1, "donor_event": 1, "x": 1, "y": 1},
 {"type": "add_monster", "map_id": {"from_step": 1}, "template_event": {"from_step": 4}, "x": 10, "y": 5, "name": "Rat", "troop": {"from_step": 3}, "graphic": {"sprite": "grey rats"}}]}
```

```bash
python tools/vxace_recipe.py plan cave.json --project "C:/Games/MyGame" --output "C:/VXWork/cave-plan"
python tools/vxace_recipe.py run cave.json --project "C:/Games/MyGame" --work "C:/VXWork/cave-run"
python tools/vxace_smoke.py check FINAL_COPY --start-map NEW_MAP_ID --x 10 --y 12 --direction 8 --expect-event Rat --auto-battle win --screenshot cave@120 --results "C:/VXWork/cave-check"
```

`plan` predicts the new map id and prints a balance table for the new troop; `run` prints the final copy.

The exact keys of every step are in [references/recipes.md](references/recipes.md). `plan` refuses a recipe that does not fit your project before anything is copied.

## Safety model

- Analysis, indexing, planning and impact are read-only and write their reports outside the project.
- Changes are first made on a disposable copy. Every targeted data file must round-trip byte-for-byte immediately before it is changed, and the copy is re-indexed and diffed afterwards.
- A reviewed copy enters your project only through [adopt](references/adopt.md): you confirm the exact file list, replaced files are backed up and `undo` restores them.
- `--in-place` recipes are only for a project you designate as a working or test project: one verified backup first, rollback on failure, one-command undo.
- Host-Ruby syntax checks are diagnostics, not proof of RGSS3 compatibility, and in-engine smoke checks supplement, never replace, your own playtesting.

## Evidence and limits

Each operation's reference records its native evidence: a small editor-made project, disposable copies and controlled fixtures. It does not prove compatibility with every customised game; review custom scripts and save hooks. The development test suite is kept locally and is not part of the published skill.

## License

[MIT](LICENSE). The vendored Python Marshal codec keeps its own MIT notice in `tools/_vendor/`. The skill contains no RPG Maker default scripts or assets; you need your own licensed copy of RPG Maker VX Ace.
