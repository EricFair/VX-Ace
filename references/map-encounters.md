# Guarded existing-map encounter append — v1.12

Use this to add **one** random encounter to the `encounter_list` of an existing native VX Ace map. It does not edit or delete existing encounters, create troops, change enemies, paint regions, resize maps, author scripts or write save files. Region painting is a separate guarded operation (`references/map-region-editing.md`).

## Snapshot and spec

Generate a fresh external Project Reader index and capture exact native preconditions:

```powershell
python tools/vxace_map_encounters.py PROJECT_INDEX --project PROJECT --map 1 --output NEW_EXTERNAL_SNAPSHOT
```

The read-only snapshot validates the native map, compares it with the indexed map and writes `map-encounter-snapshot.json`: the map SHA-256, the current encounter count and list (`troop_id`, `weight`, `region_set`), `encounter_step`, the Troops array SHA-256, the valid troop ID range, troop names and the count of cells painted with each region ID. Output must be new and outside the project/index. A snapshot never authorizes mutation.

Use its actual hashes and count in a concrete reviewed spec:

```json
{
  "title": "Reviewed map encounter",
  "changes": [
    {
      "kind": "map_encounter",
      "locator": {"map_id": 1},
      "proposal": "Add the reviewed slime troop to the whole map.",
      "mutation": {
        "action": "append_encounter",
        "expected_map_sha256": "REPLACE_WITH_SNAPSHOT_MAP_SHA256",
        "expected_encounter_count": 0,
        "expected_troops_sha256": "REPLACE_WITH_SNAPSHOT_TROOPS_SHA256",
        "troop_id": 2,
        "weight": 10,
        "region_ids": [],
        "encounter_step": null
      }
    }
  ]
}
```

## Rules

- `troop_id` must be an existing static troop in `Data/Troops.rvdata2`. The file is read-only, bound by `expected_troops_sha256`, and must be a dense `RPG::Troop` array (every slot 1..n a troop with its own ID, no nils or aliases).
- `weight` is an integer 1..100. `region_ids` has 0..32 unique integers 1..63 and is stored sorted; an empty list means the whole map. Booleans, floats, strings and unknown fields are refused.
- `encounter_step` is `null` (leave unchanged) or an integer 1..999, which sets only `@encounter_step`.
- A new entry duplicating an existing (troop, region set) pair is refused.
- The native map must have exactly the standard `RPG::Map` fields. Existing entries are admitted only when each is an `RPG::Map::Encounter` with exactly `@troop_id`, `@weight` (1..100) and `@region_set` (unique 1..63); anything else, aliased entries or a non-integer `encounter_step` is refused rather than guessed. The new object is built from scratch with that same schema and appended last.
- `expected_map_sha256` (hash of the full native map), `expected_encounter_count` and `expected_troops_sha256` must match exactly.
- Candidate verification requires the old list to be an unchanged prefix, the appended object to equal the approved factory result, and everything else — map Table, events, display name, note and unknown fields/aliases — to serialize identically (except the optional `encounter_step`).
- One `map_encounter` per transaction. It cannot be combined with any other change to the same map file or to Troops. The explicit `--backend python` copy workflow with mandatory re-indexing is required; the Ruby backend and `--no-reindex` are refused.

## Review and disposable staging

```powershell
python tools/vxace_patch_planner.py PROJECT_INDEX --project PROJECT --spec encounter-patch.json --output NEW_PLAN
python tools/vxace_impact.py PROJECT_INDEX --spec encounter-patch.json --json NEW_IMPACT.json --markdown NEW_IMPACT.md
python tools/vxace_copy_patcher.py PROJECT_INDEX --project PROJECT --spec encounter-patch.json --copy NEW_COPY --audit NEW_AUDIT --backend python
```

The impact report lists the existing encounters, the chosen troop with its member enemies and page count, and region usage: for each selected region how many cells of the map are painted with it (a region-restricted encounter on an unpainted region can never fire). It adds bounded literal script mentions of `encounter_list`, `make_encounter_list`, `encounter_step` and related classes. Remember that a random battle also needs the player to walk on the map with encounters enabled; events or scripts may disable them, and custom encounter logic is invisible to literal search.

After staging, the copy gets normalized and semantic diffs, complete post-copy byte validation and a clean selected-map tile audit. The audit records the before/after encounter lists and rollback evidence. Any apply, re-index or post-check failure removes the whole partial copy and keeps the failure audit. Originals stay unchanged.

## Version and old-save behaviour

The engine keeps `encounter_list` inside the map object stored in `$game_map`, so an old save would keep its stale list. As with region and event-structure edits, the transaction advances `System.version_id` exactly once. The default engine then calls `$game_map.setup` for the current map when an older save is loaded, re-reading the edited file. This can reset map-event state per normal engine behavior; review custom persistence hooks and do not promise lossless general save migration.

## Required native checks

- Open the map's properties in VX Ace and confirm the new encounter row, troop, weight and regions (do not save unrelated changes).
- Start a new game and walk the intended area (whole map or painted region) with encounters enabled; confirm the troop appears and region-restricted rows do not fire elsewhere.
- Load an unchanged older save and verify the map reloads with the new list; create a save, restart the Game process and load again.
- Review the troop's enemies and battle events, and any scripts that disable or replace encounters.
- Confirm source hashes, the map Table/events and Troops stay unchanged.

Public tests use original synthetic data, including an independently Ruby-produced map and dense Troops fixture, and cover bounds, duplicates, schema refusals, stale guards, candidate tampering, snapshot safety, the complete copy chain with version advance, backend/combination refusals and rollback. Native evidence is recorded below.

## Native evidence (v1.12)

On an editor-created project copy holding appended troop 31, one `append_encounter` (whole map, weight 10, `encounter_step` 5) passed the planner/copy-patcher postgates and advanced `System.version_id`. A smoke run confirmed the live `encounter_list`/step and that `Game_Player#make_encounter_troop_id` returned 31; walking with virtual input started a random battle against troop 31. Starting from a save written before the change reloaded the map with the new encounter, confirming the version-advance rule. Editor display was not inspected.
