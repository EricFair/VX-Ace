# Changelog

Writes land on a disposable copy behind exact native guards; the project changes only through adopt or a confirmed in-place recipe run. Operation details and limits are in the linked references.

## 2.0.1 — Docs cleanup

- Removed outdated and contradictory statements across the references, workflows and root docs: every doc now describes the three ways a change reaches a project (copy chain, adopt, confirmed in-place run).
- Removed development-only detail (test counts, CI, private test-project names) and duplicate sections; `tools/README.md` is a current tool index.
- No tool behaviour changed.

## 2.0.0 — Hardening

- **Faster recipes:** a content-hash cache (`tools/vxace_cache.py`) skips re-decoding and re-round-tripping files that did not change. One step went from about 43 s to about 10 s. The cache lives in the work folder and is deleted after the run. Failed gates are never cached.
- **Balance before running:** `vxace_recipe.py plan` estimates every new troop against the starting party (`balance.md`, `--balance-levels`).
- **`set_fields` actor graphics:** character and face sheets are bound by their hashes, as in an actor append.
- **Behaviour defaults from playtests:**
  - `add_monster` approaches the player (speed 3, frequency 5) and starts its battle on touch.
  - A graphic-less touch page defaults to priority below, so a door, trap or cutscene tile is stepped onto instead of acting as an invisible wall.
  - The plan warning for bare `fill_floor` points to the layout presets.
- **Smoke:** every run records its frame rate. RGSS pauses while its window is inactive, so the game window stays visible (measured: hidden, minimised and no-activate launches stall at boot).
- **Docs:** SKILL.md routing is grouped by goal and has a building loop. The README is shorter, and its recipe example was planned, run and checked in the engine.
- **Tests:** they use a frozen copy of the test project, never the live one.

## 1.34.0 — Analysis and test helpers

- **RTP auto-detection:** the RTP is found through the registry, Steam libraries and the common-files folder, so the master pass no longer flags hundreds of stock files.
- **Project overview:** a one-page summary of maps, events, custom scripts and switch/variable use.
- **RTP sprite catalogue:** covers 48 sheets, and `graphic: {"sprite": "grey rats"}` looks a sprite up by description.
- **Troop balance:** hit/evasion, damage per turn, and turns to survive.
- **Smoke helpers:**
  - `vxace_smoke.py check` runs a quick feature check on one temporary copy and deletes it afterwards.
  - A scripted DSL: `goto`, `step`, `talk`, `wait_until`, `auto_battle` and `screenshot`.
  - In-engine PNG screenshots (about 250 ms each).
- **Fixed after the first real-engine run:** event lookup, the encoding name, `step` during the transfer fade-in, and waits during auto-driven battles.
- **Checked on the test project:** RTP detected via the registry. The market check found its NPCs and saved a screenshot. On the v1.30 map, `step up:2` bumped the slime, `auto_battle :attack` won in 4 turns, and a screenshot was saved.

## 1.33.0 — Shops, inns and intros

- **New commands:** Shop Processing (302/605, the same rows as `add_shop` and the editor) and Recover All (314) are now available in event pages and common events.
- **Dialogue graphics:** dialogue events can have a graphic, and then default to priority same.
- **New macros:**
  - `add_shopkeeper`: a visible NPC that is the shop. It can stay closed until a condition is met.
  - `add_inn`: the player pays, and the party is fully healed.
  - `add_intro`: runs once on map entry, as a bounded stand-in for autorun.
- **Checked on the test project:** a new test map (Test: v1.33 Market) showed the following in the engine:
  - the grocer was solid and opened its shop;
  - the smith stayed closed until variable 20 was set, then sold;
  - the inn took 10 G and healed a party member at 1 HP to full;
  - the intro waited its 45 frames, ran once and switched itself off.

  See [shops and inns](references/shops-and-inns.md) and [intros](references/intros.md).

## 1.32.0 — Tool hazards fixed

- **Features overrides:** `features_add` and `features_remove` change single rows without retyping the template. A full replacement that drops the HIT row is refused (enemies, classes, and actors whose class lacks HIT) unless `allow_drop_hit` is set. Dropped template rows are listed as a warning.
- **Editing existing entries:** the new recipe step `set_fields` (guarded `edit_database_entry`) edits an existing entry with the same whitelisted overrides as an append, so tuning no longer means rebuilding.
- **Names:** `set_system_fields` can name switches and variables, which removes the "unnamed" warnings from later steps.
- **Balance:** the balance analysis now includes hit and evasion and warns "enemy can never hit".
- **Checked on the test project:**
  - the HIT-less replacement was refused with an explanation;
  - a `set_fields` step retuned the Cave Troll and changed its fire rate to x2 in place, keeping HIT 75% and CRI 15% in the engine;
  - 10 switches and 2 variables were named.

## 1.31.0 — Readable maps

- Fresh maps and `add_area` accept a `layout` with these parts:
  - an A5 floor;
  - an impassable 1-tile border wall;
  - visible L-shaped paths from an anchor to listed points;
  - B–E landmarks;
  - `exterior`, `interior` and `dungeon` presets for the stock RTP tilesets.

  `add_area` paths automatically run from the arrival to the return door and open the wall there.
- Plan and impact warn when a placed event can't be reached from the start, the arrival or a transfer destination.
- Verified with screenshots in the real engine: a clearing (meadow, cliff border, dirt paths, boulder, well, flowers) and a hut (wood walls, plank floor, red carpet path from the door, tables, barrel, crate). See [map layouts](references/map-layouts.md).

## 1.30.0 — Events that behave

- **Collision by default:** staged pages with a character graphic now default to priority same, so they collide and fire when the player faces them. Impact and plan warn about a graphic event below the player.
- **`add_monster` macro:** builds a map monster that starts its battle on touch. It can be fixed (bump into it), wandering, or chasing (`approach`). It is one-time (it disappears after a win) or respawning, and it can optionally be gated by a quest condition.
- **Locked doors:** `add_area` doors can be locked behind a condition, with their own locked text. Doors that have a graphic default to the action trigger with priority same.
- **Engine check on the test project:**
  - the sprite NPC collided;
  - bumping the fixed monster started its battle, and it vanished after the win;
  - the chasing monster moved toward the player;
  - the locked door opened only once its variable condition held.

See [monsters](references/monsters.md).

## 1.29.0 — In-place recipes and cleanup

- **In-place runs:** `vxace_recipe.py run --in-place --confirm-in-place NAME` builds a recipe directly in a project the user designates as the working or test project.
  - One verified backup is taken first.
  - Every gate runs per step, and only the files each step verified are promoted into the project.
  - A failure rolls back by default, and one command undoes the whole run.
  - No project copy is kept.
- **Copy-chain cleanup:** copy-chain runs now delete per-step indexes and intermediate copies by default (`--keep-intermediate` keeps them).
- **Relative paths:** reports store paths relative to the work folder, so moving it no longer breaks `adopt plan --recipe`.
- **Verified on the test project:** a 5-step recipe built a test map, an NPC and a new start position in place in 157 s. It kept a 26 KB backup and left no copies, and the new game started there.

## 1.28.0 — Classes

- Database append gains classes, configurable through:
  - EXP parameters;
  - generated stat curves (exact level-1 and level-99 endpoints, linear, early or late);
  - learnings;
  - class features (skill, weapon and armor types, equip fix and seal, dual wield, action plus, special flags).

  Recipes can teach a new skill and give the class to a new actor in the same run.

  Verified in the real engine: a new Battle Mage actor started with base MHP 400 and MAT 30 and reached exactly 6000, 1500 and 700 at level 99. Its early MMP curve ran ahead of its late MAT curve at level 50. It learned the new Spark at level 3 and skill 2 at level 8. The dry-run predicted every id. See [database append](references/database-append.md).

## 1.27.0 — Enemy actions and drops

- Enemy appends can now override action patterns: a skill, a rating, and a condition (always, turn, HP%, MP%, state, party level or switch). They can also set the three drop slots and features such as element and state rates. These are encoded exactly as the editor saves them (for example, the empty drop slot is kind 0 / id 1). Recipes can point actions at a new skill and drops at a new item. Verified in the real engine:
  - an Acid Slime only attacked at full HP and always chose its new rating-9 Acid skill below half HP;
  - the slime dropped its Potion and took double fire damage;
  - a boss's every-third-turn skill was valid on turns 3 and 6 only;
  - the dry-run predicted every id.

  See [database append](references/database-append.md).

## 1.26.0 — New areas

- **Fresh-map mode for blank-map append:** when width, height and tileset are given, any existing map serves as the schema template. The new map gets the editor's new-map defaults (checked against an unedited editor project) and an optional passable A5 floor fill.
- **Blank events:** they can take their schema from another map's event.
- **Recipes:** they can pass a new map's id to later steps.
- **`add_area` macro:** builds a new map with a door in and a return door out, refusing door/arrival bounces.
- **Verified in the real engine:**
  - On the user's 100x100 map, a touch door led into a new 25x20 cave arriving at the set tile and facing.
  - The cave had a walkable A5 floor and no encounters or music.
  - A chest placed in the cave through `from_step` worked.
  - The return door led back.
  - The dry-run predicted every id.

  See [new areas](references/new-areas.md).

## 1.25.0 — NPC movement and touch triggers

- Staged pages get player-touch, event-touch and parallel triggers (autorun stays refused), plus autonomous movement: random, approach, or a bounded custom route. The command language gains Set Move Route for the player or this event, with deadlock-prone combinations refused, and Erase Event. A new `add_touch_trigger` macro builds a one-time or repeatable step-on trigger. Verified in the real engine: a villager wandered, a guard paced exactly between three tiles, a step-on cutscene moved the player two tiles up once, a trap took gold once, and an event erased itself. The dry-run predicted every id. See [touch triggers](references/touch-triggers.md).

## 1.24.0 — Recipe dry-run

- `vxace_recipe.py plan` runs the validator gate and then simulates a whole recipe in memory, without making any copy. For every step it reports the predicted id, resolved `from_step` links, a summary and warnings, plus the files that will change, the transaction count and a disk estimate. All id-creating steps are predicted exactly; `text_import` is marked "predicted, verify after run". On an editor-saved project, the plans for an actor/System recipe and a chest recipe matched the real runs' ids and parameters exactly, in 10–16 s each, with the project unchanged. See [recipes](references/recipes.md).

## 1.23.0 — Actors and System fields

- Database append gains actors: class, levels, nickname, character and face graphics (asset-bound), and equipment checked against slot, equip type and class rules. A new guarded `set_system_fields` edit sets the starting party, start position, game title, currency unit and menu terms. Recipes can put an actor appended earlier into the starting party or a party command. Verified in the real engine: a new game started at the new position, with the new actor leading the party in her own graphics and equipped weapon, and with the new title and terms; an old save kept its own party but showed the new terms. See [database append](references/database-append.md) and [system fields](references/system-fields.md).

## 1.22.0 — Treasure chests

- The shared command language gains Change Weapons/Armors (127/128, bound by their own hashes), and staged pages can set a character graphic and page options. The new `add_treasure_chest` recipe macro builds a closed/opened two-page chest holding gold, an item, a weapon or an armor (also one appended earlier in the recipe). Verified in the real engine with the RTP `!Chest`: chests gave their contents once, switched to the opened frame, and stayed open. See [treasure chests](references/treasure-chests.md).

## 1.21.0 — Common events

- `append_common_event` adds one call-only or switch-gated parallel common event using the staged-event command language (autorun and self switches refused; parallel needs a wait). Referenced databases are bound by their own hashes; recipes can call it from staged events and from item/skill effect 44. Verified in the real engine: an inn charged 50 gold or took its else branch, a parallel timer ticked only while its switch was ON, and an item's effect 44 ran a common event. See [common events](references/common-event-append.md).

## 1.20.0 — Usable items, effects and features

- Database append gains usable items (template clone; key items stay with `append_key_item`) and bounded full-list overrides of skill/item **effects** and weapon/armor/state **features**, with editor-matching Integer/Float encodings. Every referenced States/Skills/CommonEvents/System file is bound by its own hash; recipes can point effects and features at a state or skill appended earlier. Verified in the real engine: a Hi-Potion healed 50% and cured a new state, an Ether restored 30 MP, and a Poison Dagger carried its attack state, attack element, hit bonus and element rate. See [database append](references/database-append.md).

## 1.19.0 — Branching event commands

- Staged event pages gain Show Choices with branches, Conditional Branch (switch, variable, self switch, gold, item) with else, Battle Processing with win/escape/lose branches, Change Party Member, Call Common Event, Change Gold/Items, Transfer Player and Wait; nesting up to 4 levels. Each referenced database and destination map is bound by its own hash; recipes can feed a new troop or key item into a battle or item check. Verified in the real engine: a choice recruit, a locked/open door and a boss battle lost into its lose branch. See [staged events](references/staged-events.md).

## 1.18.0 — Quest-stage events

- `append_staged_event` builds one event with 1..8 action-button pages (switch, variable and self-switch conditions), literal dialogue and Control Switches/Variables/Self Switch commands; recipe step `append_staged_event`. Verified in the real engine: three talks advanced a quest NPC through all pages. See [staged events](references/staged-events.md).

## 1.17.0 — Adopt and daily workflow

- `vxace_adopt.py plan/apply/undo/status` brings a reviewed staged copy (single audit or recipe) into the working project: drift, undeclared-difference and smoke-harness refusals, editor/game-running refusal, per-file backup, atomic writes with rollback, verified undo. Verified on a stand-in project: recipe → plan → apply → real-engine smoke run → byte-identical undo. See [adopt](references/adopt.md).
- New [daily game development](workflows/daily-game-dev.md) guide and a rewritten [getting started](GETTING_STARTED.md) with Claude Code and Codex installs; SKILL.md boundary 8 named adopt as its exception (in-place recipe runs were added in 1.29).

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
