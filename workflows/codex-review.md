# Workflow — Project Codex Review

Use this workflow when a v0.6 codex is available.

## 1. Start with the high-level candidate

Search `codex/index.json` / `codex/systems.json` / `codex/state-machines.json` for the system closest to the user's request.

Do not assume the candidate label is correct merely because confidence is high.

## 2. Inspect evidence

For every project-specific claim that matters, follow the candidate's evidence to:

- map ID / event ID / page / command index;
- common-event ID / command index;
- switch/variable ID and symbolic name;
- troop/map target;
- script path/order/method collision.

## 3. Use the specialized views

- `codex/maps.json` for map/event/page dependencies;
- `codex/scripts.json` for script ownership/order/collision context;
- `codex/graph.json` for relationship traversal;
- raw `analysis/*.json` when the codex summary is insufficient;
- normalized `maps/*.json` / `database/*.json` for exact source truth.

## 4. Separate fact from inference

State clearly whether a statement is:

- **verified project fact** — directly present in normalized project data;
- **derived relationship** — deterministically connected from indexes;
- **codex inference** — heuristic system interpretation;
- **hypothesis** — debugging explanation not yet proven.

## 5. Never manufacture stage meanings

An observed progression value is not a semantic label.

If Variable 21 is assigned `2`, report `2` unless project evidence proves what `2` means.

## 6. Debugging path

For a probable quest/system bug:

1. identify the codex system/state machine;
2. inspect all evidence locations touching the relevant state;
3. trace reads/writes in chronological game logic;
4. inspect page conditions and common-event callers;
5. inspect related Ruby scripts/order if event Script commands or custom frameworks participate;
6. propose the smallest falsifiable fix;
7. regression-test adjacent states/transfers/save-load behavior.

## 7. Freshness

Regenerate the Project Reader + Codex after project changes. Do not treat an older codex as authoritative once the source project has changed.
