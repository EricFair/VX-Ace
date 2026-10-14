# Dependency Impact and Semantic Codex Diff — v0.10

## Purpose

v0.10 improves understanding before and after a staged VX Ace change without increasing binary write power.

`vxace_impact.py` consumes a fresh Project Reader/Codex index plus an existing patch specification. It verifies the direct target and surfaces one-hop evidence from the Codex graph, script ownership/collision metadata, save hooks, and database identity.

It is a **review aid**, not proof that no hidden dependency exists. Dynamic Ruby, unindexed event-command shapes, note-tag consumers, and database references can still escape static extraction.

## Impact rules

- Map event target: require exact `map_id`, `event_id`, and `page`; report graph relationships for that page.
- Common event: require an indexed `common_event_id`; report callers/readers/writers represented in the graph.
- Troop: require an indexed `troop_id`; report known battle-gate relationships, with an explicit completeness warning.
- Script: require exact extracted script path; report classes, methods, aliases, `$imported` metadata, save hooks, and collision candidates.
- Database: require exact table + ID and verify the object exists. Full database dependency edges are not yet available, so this remains a verified direct target.

## Semantic diff

`vxace_semantic_diff.py` compares two Project Codex snapshots and reports changes in:

- inferred systems;
- state-machine candidates;
- graph nodes;
- graph edges;
- script ownership/collision metadata.

A semantic diff can show that a patch changed project meaning even when the expected raw file was the only file modified. Conversely, a changed heuristic inference is still not proof of intended game semantics; follow the evidence back to the normalized source.

## Safety interpretation

Impact analysis and semantic diffing never authorize broader mutation. Real-project v0.9 validation is still required before enabling structural event/page insertion or arbitrary binary editing.
