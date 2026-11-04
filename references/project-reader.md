# VX Ace Project Reader — Architecture

## Goal

Convert a legally accessible RPG Maker VX Ace project into a separate normalized index that an agent can inspect efficiently without rereading opaque `.rvdata2` files and without modifying the source project.

## Components

### `vxace_project_reader.py`

Python orchestration layer. It owns:

- project discovery;
- source inventory and hashes;
- output layout;
- database/map extraction requests;
- Scripts archive extraction;
- event-reference indexing;
- compatibility-analyzer invocation;
- project summary/error reporting.

### `rvdata2_bridge.rb`

Read-only Marshal decoder. It:

- defines inert standard `RPG::*` class stubs;
- defines inert RGSS native stand-ins for `Table`, `Color`, `Tone`, and `Rect`;
- calls `Marshal.load` on project data;
- never loads/evals project script source;
- converts loaded objects into JSON-shaped data;
- inflates the compressed entries in `Scripts.rvdata2`.

## Trust boundary

Treat project data as untrusted input.

The bridge must not:

- `eval` script strings;
- `require` extracted scripts;
- instantiate application-specific behavior beyond inert data stubs;
- write to source files;
- place generated output in `Data/` or elsewhere inside the source project.

## Provenance

`manifest.json` records source file paths relative to the project, file sizes, and SHA-256 hashes. It intentionally omits the absolute source path by default.

Every event-derived reference retains a normalized command path. Map event references additionally expose map ID, event ID, page number, and command index when the standard data shape is present.

## Event commands indexed

High-value relationships currently include:

- `117` — Call Common Event;
- `121` — Control Switches;
- `122` — Control Variables;
- `123` — Control Self Switch;
- `111` — Conditional Branch switch/variable reads;
- `201` — Transfer Player;
- `301` — Battle Processing;
- `355` + `655` — Script command blocks.

The reader preserves full normalized map/common-event data, so later versions can add more command-specific relationship extraction without rereading the binary project.

## Name resolution

When available, the reader resolves:

- switch names from `System.rvdata2`;
- variable names from `System.rvdata2`;
- map names from `MapInfos.rvdata2`;
- common-event names from `CommonEvents.rvdata2`;
- troop names from `Troops.rvdata2`.

## Failure model

Extraction is best-effort per file. If one `.rvdata2` file cannot be decoded:

- the source is left untouched;
- other files continue processing;
- `project.json` records the error;
- CLI exit code indicates partial extraction.

## Backends

The orchestration/index format should remain independent of the Marshal backend.

The pure-Python Ruby Marshal 4.8 backend (`vxace_python_mutator.py`) can replace the Ruby bridge without changing the project-index contract. It preserves unknown objects/user-defined payloads; writers run only after the byte-identical round-trip gate passes (see [project validation](project-validation.md)).

## Operand metadata and transfers

The reader preserves additional Control Variables / Conditional Branch operand metadata so downstream analysis can distinguish an observed constant assignment/comparison from a generic read/write.

For direct map transfers, the index preserves `source_map_id` separately from the destination `map_id`. This avoids treating the destination map as the event context that initiated the transfer.

Unless `--no-codex` is supplied, ingestion runs `tools/vxace_codex.py` after deterministic indexes and compatibility analysis are generated.

## Project overview (v1.34)

After the Codex, the reader runs `tools/vxace_overview.py` and writes **`overview.md`** and **`overview.json`** into the index folder (`project.json` `overview_generation`; skipped with `--no-codex`). Run it alone with `python tools/vxace_overview.py INDEX [--output DIR]`. It reads only the index and never touches the project. The master report links to `index/overview.md`.

The page has:

- **Maps:** id, name, display name, size, tileset (id and name), event count; the start map, position and party from System.
- **Events per map:** every event (name, x,y) and each page with trigger, priority, graphic, condition and a one-line summary of the first six actions: text first line, choices, conditionals, switch/variable/self-switch writes, gold/item changes, transfer target, battle troop name, shop goods, common event calls, scripts. Up to 60 events per map in the markdown (the JSON keeps all).
- **Custom scripts:** the scripts between `▼ Materials` and `▼ Main Process` that have source, with their classes/modules and `alias`/`alias_method` lines.
- **Switches and variables in use:** id, name, which maps/events/common events/troops read and write them (from the reader's reference index).
- **Database:** entries per table and the entries above the stock slot counts of an unedited new project (actors 10, classes 10, skills 126, items 16, weapons 60, armors 60, enemies 30, troops 30, states 25, animations 110, tilesets 4, common events 10; read from the editor's `project2.zip`), so the author's additions stand out.

Limits: the summaries are not a behaviour proof; script-set switches/variables are invisible; a project from another template lists its own entries as new.
