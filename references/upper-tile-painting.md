# Ordinary upper-layer scenery painting — v0.25

`map_tile` / `paint_upper_tiles` changes1..256 unique cells on **graphic layer2 only**, using ordinary B-E IDs0..1023. Zero clears an upper tile. Ground layers0/1, A5/autotiles, shadows, regions, map size/tree and all other map fields stay untouched. Existing upper autotiles/A5 values are refused rather than converted; no neighbor-autotile synthesis, fill algorithm or map creation is enabled.

## Obtain exact native and asset evidence

Run a fresh complete reader/master workflow, then select cells and prospective tile IDs from the actual native tileset:

```powershell
python tools/vxace_upper_tiles.py PROJECT_INDEX --project PROJECT --map MAP_ID --cell X Y --tile TILE_ID --rtp EXPLICIT_RTP_ROOT --output NEW_PRIVATE_SNAPSHOT
```

Repeat `--cell` and `--tile` as needed. Omit `--rtp` only when all selected assets resolve in the project. RTP is an explicit separate read-only root; no installed-resource discovery, installation or copying occurs. Snapshot output must also be outside RTP.

The snapshot rechecks the exact native/indexed map Table, tileset identity/names/8192 flags, current upper cells, per-cell static passage, proposed tile routing/flags, and selected image bindings. Names and flags come from the actual map's tileset; never substitute a guessed exterior sheet for a field/dungeon/interior map. The selected tileset's full native object SHA includes unknown fields without modifying them.

Image resolution is project-first with explicit RTP fallback. Empty/unsafe sheet names, missing/ambiguous/case-mismatched files, non-PNG sheets or nonstandard512x512 headers are refused. Selected files must be regular/unlinked and <=32MiB, with stable descriptor/path metadata, valid bounded PNG IHDR/CRC and exact full-file SHA-256. Catalog rechecks detect competing/changed resolutions. Header/layout checks **do not prove full decoding**; native editor/runtime acceptance remains required. The empty B tile must retain its native star flag.

## Concrete spec

Use `upper-tile-snapshot.json` to populate these fields, with one reviewed cell list:

```python
mutation = {
    "action": "paint_upper_tiles",
    "expected_table_sha256": snapshot["table_sha256"],
    "expected_tileset_sha256": snapshot["tileset_sha256"],
    "expected_assets": snapshot["assets"],
    "cells": [{"x": reviewed_x, "y": reviewed_y,
               "expected_tile": captured_current_upper_tile, "value": reviewed_new_tile}]}
spec = {"changes": [{"kind": "map_tile", "locator": {"map_id": captured_map_id},
                     "proposal": "Paint the reviewed ordinary upper scenery cells.",
                     "mutation": mutation}]}
```

Asset bindings must cover every nonzero **current and proposed** selected tile's sheet. Preserve their exact slot/name/origin/path/hash/dimensions. Re-snapshot after changing prospective IDs or source assets. No-op, duplicate, stale, out-of-bounds, boolean, layer override and unsupported IDs are refused. Native maps must be1..500 by1..500 with an exact four-layer Table. This operation neither edits the tileset nor changes its flags.

## Guarded copy transaction

```powershell
python tools/vxace_patch_planner.py PROJECT_INDEX --project PROJECT --spec PRIVATE_SPEC --output NEW_PLAN
python tools/vxace_copy_patcher.py PROJECT_INDEX --project PROJECT --spec PRIVATE_SPEC --copy NEW_DISPOSABLE_COPY --audit NEW_AUDIT --backend python --rtp EXPLICIT_RTP_ROOT
```

The Python backend and mandatory re-indexing are required. Use one upper operation per map with no other mutation to that same map in the transaction. Copy/audit output cannot be inside source or read-only RTP. Fresh source/index, complete selected-backend project byte gates, immediate target gates, exact per-cell/Table/tileset/asset preconditions, proposed dependency impact, candidate verification, selected-map diagnostics, semantic diff and complete post-project validation remain mandatory.

The low-level Python worker requires the actual canonical native `Data/MapNNN.rvdata2` input path and explicit asset context. It independently reads adjacent native Tilesets and selected real assets before applying; a JSON claim alone cannot bypass these checks. It detaches the map Table from unknown aliases. Candidate verification permits only the approved two-byte words on layer2 and preserves the complete other Table bytes/shape and unrelated native fields. Assets are rechecked at final acceptance; failure removes the whole staged copy and retains the failure audit. Source/RTP files are never changed by the writer.

Upper painting advances the copy's native System.version once, shared with any supported map/event edits on other targets. This makes default older-save loading reload map data. Custom save/map hooks and runtime map replacement still require review; an asset/serialization pass never authorizes automatic promotion to a working project.

## Native testing and limits

Review directional passage, star priority, terrain, bush/ladder/counter/damage-floor flags and event/runtime consumers. A visually small overlay can change movement because native flags determine passage through the tile stack. Impact reports bounded literal consumer evidence, not complete behavior or dynamic map ownership.

The private independent editor fixture painted an actual Field/World_B sign and tent. Saving in VX Ace changed exactly two layer2 cells and no ground/shadow/region words. The guarded candidate's complete Table payload matched that editor result; unrelated source fields were preserved. Whole map files are not claimed identical: the editor separately reserialized its event graph.

Native disposable testing loaded an unchanged older save, observed the version-driven map reload and painted tile IDs, blocked player movement into the sign and allowed movement onto the tent, then restored the player position and saved once. A new Game process loaded that save with the same tiles and position, no extra map setup and no save rewrite. Source, other database files and original-project hashes remained unchanged. These results apply to the inspected native fixture, not all custom map/save scripts.

All 364 executable tests passed locally, including 12 upper-tile checks using authored PNGs and synthetic data, C/D/E bindings and refusal/rollback cases. All seven read-only master stages passed on the native source copy. Proprietary resources, games, saves, generated bundles and raw reports stay private. Broad ground/autotile painting, map resize/tree changes, general fill and arbitrary layer writes remain deferred.
