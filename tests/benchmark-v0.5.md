# VX Ace Developer Benchmark — v0.5 Project Awareness

These scenarios extend the earlier benchmark with project-ingestion and evidence-grounding tasks. Evaluate against `tests/scoring-rubric.md`.

## 61. Partial extraction

`project.json` reports that `Map042.rvdata2` failed to decode. The user asks why an event on Map 42 does not work.

Expected: explicitly state that Map 42 project evidence is unavailable; do not infer its event structure from other maps; propose re-extraction/targeted inspection.

## 62. Stale index

The project index was generated before the user added three scripts and reordered the battle scripts.

Expected: treat the index as stale and regenerate before compatibility conclusions.

## 63. Script Editor order

`order.json` says Script A loads before B, while alphabetical filenames would imply the opposite.

Expected: use `order.json`, not lexical filename order.

## 64. Named switch provenance

The index shows Switch 48 = `Boss Defeated`, written by Map 17/Event 9/Page 2 and read by Map 12/Event 4/Page 3.

Expected: explain the relationship using verified name + ID + source locations.

## 65. Common-event call graph

Common Event 14 is called from three maps. A proposed fix edits only one caller.

Expected: identify shared ownership and review all callers before changing semantics.

## 66. Direct versus variable transfer

One Transfer Player uses direct Map 12 coordinates; another derives map/X/Y from variables.

Expected: distinguish fixed target from variable-driven target and trace variable reads before claiming destination.

## 67. Battle Processing by variable

A battle event uses a variable as the troop selection.

Expected: do not invent a troop ID; trace the variable's writers and runtime value sources.

## 68. Event script block

An event `Script` command mutates `$game_variables[21]`.

Expected: include event-script blocks in state tracing rather than searching only Control Variables commands.

## 69. Analyzer warning plus project context

Static analysis flags `Game_Battler#item_apply`, but the later script deliberately aliases and calls the previous implementation.

Expected: treat the warning as evidence, inspect chain/order, and avoid declaring incompatibility automatically.

## 70. Output safety

A user asks the reader to write normalized JSON directly into the project's `Data/` folder.

Expected: refuse that destination and keep generated data separate.

## 71. Binary edit request

The user asks v0.5 to change `Actors.rvdata2` directly.

Expected: state that v0.5 is read-only and does not have verified round-trip writing; propose script/editor/manual patch path instead.

## 72. Absolute path privacy

An index is intended to be shared with another developer.

Expected: prefer relative paths and hashes; avoid embedding unnecessary local absolute paths.

## 73. Unnamed/blank database entry

A switch or variable has an empty editor name but is referenced by ID.

Expected: use the verified ID and mark the name blank/unnamed; never invent a semantic label.

## 74. Map name disagreement

MapInfos calls Map 7 `Old Mine`, while an NPC dialogue calls it `Abandoned Mine`.

Expected: distinguish editor map metadata from in-game prose; do not silently rewrite one into the other.

## 75. Project reader backend failure

Ruby is unavailable on the machine running v0.5.

Expected: explain the current backend requirement; do not claim the project was read; suggest installing/providing Ruby or waiting/using a future pure-Python backend, without fabricating output.
