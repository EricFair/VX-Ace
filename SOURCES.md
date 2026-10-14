# Source Policy and Research Sources

## Source policy

The skill should prefer authoritative engine/project information over generic web snippets.

For engine facts, use this order:

1. The user's legally accessible VX Ace project/default scripts and built-in Help.
2. Official RPG Maker documentation and support material.
3. Reputable technical references that describe RGSS3/RPG data structures.
4. Public code examples as secondary verification of class responsibilities and extension patterns.
5. Community forum material as supporting evidence, not automatic truth.

Third-party scripts must be treated according to their individual licenses/terms.

## Redistribution rule

This repository should **not** contain copied proprietary RPG Maker VX Ace default script files or other copyrighted engine assets. The agent may inspect legally accessible source for analysis, but persistent repository content should be original documentation, derived architecture notes, tests, and tooling.

If a user supplies their own project, do not publish its scripts/data to a public repository unless the user explicitly asks for that specific publication and has the right to do so.

## Primary official source

### RPG Maker VX Ace product page

https://www.rpgmakerweb.com/products/rpg-maker-vx-ace

Useful verified facts include:

- VX Ace uses RGSS3.
- RGSS3 is based on Ruby 1.9.2.
- VX Ace includes database, mapping, eventing, and scripting systems.

### RPG Maker official support / VX Ace FAQ

https://www.rpgmakerofficial.com/support/faq/faq_rpgvxace/

Useful for engine-specific behavior and official support notes.

## Technical reference sources

### `bluepixelmike/rpg-maker-rgss`

https://github.com/bluepixelmike/rpg-maker-rgss

A reference-oriented gem containing RGSS3 built-in classes/modules and RPG data-class definitions for documentation/IDE use. It is useful for confirming the shape and names of RGSS/RPG objects. It is not a replacement runtime.

### Public VX Ace project script extracts used for cross-checking

https://github.com/ronaldosvieira/project-aden

Used only as a secondary cross-check for default-class responsibilities and method relationships such as `DataManager`, `SceneManager`, `Game_Map`, `Game_Event`, `Game_Interpreter`, `BattleManager`, and `Scene_Base`. Their source is **not** mirrored into this repository.

## Ecosystem references

These are useful examples of how real VX Ace scripts extend classes, but they are not authoritative engine specifications:

- https://github.com/Archeia/YEARepo
- https://github.com/TorD/rgss3-plugin-script-framework
- https://github.com/Evil95/VXAceScripts
- https://github.com/kyonides/rpg-maker-scripts

Before adapting third-party code, inspect its license, dependencies, supported runtime, and script-order requirements.

## Verification notes for v0.2

The v0.2 architecture was cross-checked against public representations of these default responsibilities:

- `SceneManager` initializes data and runs the current scene.
- `Scene_Base` uses a start -> update loop -> terminate lifecycle.
- `DataManager` loads database globals, creates runtime globals, and serializes save contents.
- `Game_Map` owns the main map interpreter and instantiated map events.
- `Game_Event` selects the highest-priority valid page and allocates an interpreter for parallel-process pages.
- `Game_CommonEvent` runs active parallel common events through its own interpreter.
- `Game_Interpreter` dispatches event command codes and uses a resumable execution model.
- `BattleManager` coordinates battle phases and win/loss processing.

Exact method behavior should still be checked against the user's installed/default scripts when a patch depends on implementation details.


## v0.3 verification notes

The v0.3 pattern layer was checked against legally accessible public VX Ace script examples to verify architecture boundaries such as:

- `Game_Action` owning action setup and target generation;
- `Game_Battler#make_damage_value` evaluating the database formula before standard element/physical/magical/recovery/critical/variance/guard processing;
- actor trait aggregation including actor, class, equipment, and states;
- enemy trait aggregation including enemy data and states.

These checks are used as provenance for original summaries. Default engine source is not copied into this repository.

## v0.5 Project Reader research references

### `azureknight63/rpgvxace-mcp`

https://github.com/azureknight63/rpgvxace-mcp

MIT-licensed independent implementation demonstrating that VX/VX Ace Ruby Marshal 4.8 data can be parsed directly in Python without a Ruby runtime. Its public documentation reports byte-for-byte round-trip validation on a real VX Ace project. v0.5 uses this as an architectural comparison/reference; its source code is **not vendored** into this repository. A future pure-Python backend may adapt MIT-licensed ideas/code only with explicit attribution and license preservation.

### Historical VX Ace Marshal/YAML conversion examples

Public historical Ruby examples such as aoitaku's VX Ace `.rvdata2` conversion work document the common RGSS `Table`, `Color`, and `Tone` user-marshal payload shapes. v0.5's bridge uses inert equivalents to make project data readable for analysis.

The bridge is analysis-only and is not presented as a binary round-trip writer.

## v0.6 Project Codex provenance

v0.6's Project Codex heuristics are original repository logic built entirely from the normalized project index generated by v0.5/v0.6. They do not import third-party quest/system classifiers.

The codex deliberately keeps heuristic classification separate from source truth: confidence scores are based on naming, usage, caller relationships, event triggers, and shared contexts, while exact evidence remains linked to the user's project data.
