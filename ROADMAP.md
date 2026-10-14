# Roadmap

## v0.3 — Event and database patterns

Target: make the agent excellent at choosing native VX Ace solutions before scripting.

Planned additions:

- reusable event patterns: one-time rewards, doors/keys, quest stages, cutscenes, shops, conditional NPCs, region-based logic;
- autorun/parallel anti-pattern catalog;
- switch/variable naming and ownership conventions;
- state/skill/equipment trait patterns;
- damage-formula boundaries and when to graduate to RGSS3;
- benchmark expansion with event-debugging cases.

## v0.4 — Script compatibility analysis

Target: reliably reason about third-party script collisions.

Planned additions:

- parser/index of class reopenings;
- method alias/override inventory;
- script-order dependency graph;
- `$imported` and dependency convention detection;
- configuration/note-tag surface inventory;
- conflict severity scoring;
- compatibility report format.

## v0.5 — Project Reader prototype

Target: ingest a real VX Ace project read-only.

Planned outputs:

- database JSON export;
- map/event JSON export;
- switch/variable tables;
- common-event callers;
- map-transfer graph;
- troop-event references;
- extracted Scripts order and Ruby files;
- script method/class index;
- hashes/provenance manifest.

## v0.6 — Project Codex

Target: transform extracted project data into durable, human-readable system knowledge.

Examples:

- quest state machines;
- boss progression chains;
- NPC/event dependencies;
- map flow;
- battle-system extensions;
- UI/menu extensions;
- save-data additions;
- project naming conventions.

## v0.7 — Patch workflow

Target: let an agent propose and apply reversible project changes.

Requirements:

- work on extracted text/structured representations;
- backup/hash before modification;
- diff every patch;
- static compatibility checks;
- explicit test plan;
- no direct binary rewrite until round-trip fidelity is proven.

## v1.0 — Validated specialist

Release criteria:

- passes full benchmark at target score;
- tested against at least one real VX Ace project;
- project-reader round-trip tested;
- compatibility analysis validated against real multi-script projects;
- safe patch/rollback workflow documented.
