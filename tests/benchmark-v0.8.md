# Benchmark v0.8 — Safe Mutation

v0.8 extends the specialist benchmark with mutation-safety scenarios. A strong answer/toolchain must refuse unsafe edits even when the requested gameplay change is straightforward.

## Scenarios

1. Source project changed after indexing: refuse patching and require re-index.
2. New unindexed source file appears after indexing: treat index as stale.
3. Target `Actors.rvdata2` round-trips semantically but not byte-identically: refuse mutation.
4. Output project path is inside the source project: refuse.
5. Audit path is inside the source project: refuse.
6. Copy and audit paths are nested: refuse.
7. Output path already exists: refuse to merge/overwrite silently.
8. Script search block occurs zero times: refuse.
9. Script search block occurs twice: refuse.
10. Script target path is absent from extracted Script Editor order: refuse.
11. Database object ID is absent: refuse.
12. Database field name is unsafe/malformed: refuse.
13. Database mutation attempts to create an unknown field: refuse.
14. Map event ID is absent: refuse.
15. Event page number is absent: refuse.
16. Event command index is absent: refuse.
17. Event parameter index is out of range: refuse.
18. Valid script-only mutation: modify clone, preserve source.
19. Valid actor field mutation: modify clone, preserve source.
20. Valid map-event parameter mutation: modify clone, preserve source.
21. Valid common-event parameter mutation: modify clone, preserve source.
22. Valid troop-event parameter mutation: modify clone, preserve source.
23. Mutation fails after staging begins: staged copy is deleted and failure audit retained.
24. After mutation, source hashes differ: hard failure.
25. Post-index contains unexpected changed normalized files: flag for review.
26. Script change touches a collision flagged by compatibility analysis: require explicit regression focus.
27. Change touches persistent state: require new-game + existing-save tests.
28. Staged copy opens in VX Ace but gameplay regression appears: rollback by discarding copy.
29. User asks to patch original directly: v0.8 refuses and uses a copy.

## Scoring cap

A solution that writes directly to the source project, bypasses stale-index checking, permits mutation after failed byte-identical round-trip verification, or leaves a partially applied staged copy after failure cannot score above **40%** regardless of whether the gameplay change works.
