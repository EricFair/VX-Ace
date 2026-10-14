# VX Ace Project Reader — v0.5 Architecture

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

## Event commands indexed in v0.5

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

## Future backend

The orchestration/index format should remain independent of the Marshal backend.

A future pure-Python Ruby Marshal 4.8 backend can replace the Ruby bridge without changing the project-index contract. The target backend should preserve unknown objects/user-defined payloads and ultimately enable proven round-trip fidelity before any write capability is considered.
