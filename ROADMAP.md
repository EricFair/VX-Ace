# Roadmap

Completed: v0.4 RGSS3 compatibility analyzer.

## v0.4 — Script compatibility analysis ✅

Delivered:

- executable read-only static analyzer;
- parser/index of class and module reopenings;
- method definition and alias inventory;
- duplicate-method collision candidates with conservative severity;
- Script Editor order support through `order.json`;
- `$imported` definition/read/load-order checks;
- constant/global write collision candidates;
- save-hook and note-parser detection;
- JSON and Markdown reports;
- `--fail-on-high` pipeline mode;
- synthetic fixtures and automated unit tests;
- compatibility scan workflow and benchmark scenarios.

## v0.5 — Project Reader prototype

Target: ingest a real VX Ace project **read-only**.

Planned outputs:

- database JSON export;
- map/event JSON export;
- switch/variable tables;
- common-event callers;
- map-transfer graph;
- troop-event references;
- extracted Scripts order and Ruby files;
- v0.4 compatibility analysis invoked automatically;
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
