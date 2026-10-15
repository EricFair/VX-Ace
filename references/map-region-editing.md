# Guarded existing-map region cells — v0.19

Use this for a small, reviewed change to region IDs on an existing native VX Ace map. It does not paint graphic tiles, change shadows, resize/create/delete maps, modify encounters, author scripts or write save files.

## Snapshot and spec

Generate a fresh external Project Reader index and capture exact native preconditions:

```powershell
python tools/vxace_map_regions.py PROJECT_INDEX --project PROJECT --map 1 --cell 8 6 --cell 8 7 --output NEW_EXTERNAL_SNAPSHOT
```

The read-only snapshot compares normalized/native map data, requires the native file's byte-identical no-op gate and returns the full Table payload SHA-256, selected cell regions and their entire lower metadata bytes. Output must be new and outside project/index. A snapshot never authorizes mutation.

Use its actual fingerprint and current regions in a concrete reviewed spec:

```json
{
  "title": "Reviewed map region change",
  "changes": [
    {
      "kind": "map_region",
      "locator": {"map_id": 1},
      "proposal": "Mark two existing cells after reviewing region consumers.",
      "mutation": {
        "action": "set_regions",
        "expected_table_sha256": "REPLACE_WITH_EXACT_SNAPSHOT_SHA256",
        "cells": [
          {"x": 8, "y": 6, "expected_region": 0, "value": 7},
          {"x": 8, "y": 7, "expected_region": 0, "value": 63}
        ]
      }
    }
  ]
}
```

The writer accepts 1..256 unique in-bounds cells, one operation per map per transaction. Expected and new region values must be native editor IDs **0..63**; booleans, no-ops, unknown fields, duplicate cells, stale fingerprints and mismatched current regions are refused. A byte can hold larger IDs, and a snapshot may expose them in an existing custom project, but this writer does not edit those nonstandard cells. Native editor testing exposed this distinction; do not broaden the range to 255 merely because the packed Table permits it.

The map must be a native `RPG::Map`, 1..500 cells on each axis, with an exact three-dimensional width × height × four-layer Table. Only the high byte of selected fourth-layer cells changes. All three graphic layers and the entire lower metadata byte—including shadows and reserved bits—are preserved. The Table is detached so unknown aliases retain their original data. Candidate verification compares every Table byte against the approved change and conservatively checks other map fields/aliases; custom self-references may refuse rather than permit an unproven change.

## Review and disposable staging

```powershell
python tools/vxace_patch_planner.py PROJECT_INDEX --project PROJECT --spec region-patch.json --output NEW_PLAN
python tools/vxace_impact.py PROJECT_INDEX --spec region-patch.json --json NEW_IMPACT.json --markdown NEW_IMPACT.md
python tools/vxace_copy_patcher.py PROJECT_INDEX --project PROJECT --spec region-patch.json --copy NEW_COPY --audit NEW_AUDIT --backend python
```

The impact report requires a clean selected-map tile audit and complete encounter/script evidence. It lists native encounter entries and their region sets, plus bounded literal `region_id`/`region_set` script mentions. Changing a region can change encounter eligibility or custom quest/movement logic. Mentions include default definitions/comments and can miss dynamic calls, note tags and external logic; inspect actual consumers instead of treating the list as a complete dependency graph. Every region change is high risk for review purposes; no automatic repair follows.

The explicit Python copy backend is mandatory. A new disposable copy is created only after fresh source/index checks, exact native preconditions, complete selected-backend project validation and immediate target byte gates. The Ruby backend, disabled re-indexing and duplicate operations on the same map are refused. A transaction containing region and/or guarded event structure edits advances `System.version_id` exactly once, so the default engine reloads the current map from disk when an older save is loaded. This can reset map-event state according to normal engine behavior; review custom persistence hooks and do not promise lossless general save migration.

After staging, require normalized and semantic diffs, complete post-copy byte validation and clean selected-map tile audits. The audit includes before/after region snapshots, approved-byte/other-field checks, dependency impact and rollback evidence. Any apply/re-index/post-check failure removes the whole partial copy while retaining the failure audit. Originals remain unchanged. The master and MCP interface remain read-only and do not invoke this writer.

## Required native checks

- Inspect the changed cells in VX Ace's Region overlay without painting or saving unrelated changes.
- Start a new game and verify native `Game_Map.region_id` results.
- Load an unchanged older native save, verify the expected map reload and preservation/reset behavior for the affected content.
- Create a save through native engine behavior, restart the Game process and load it again; confirm regions and player state.
- Test affected encounter sets and custom region consumers where applicable. Absence of consumers in a small seed is not evidence about arbitrary customized projects.
- Confirm source hashes, all unapproved Table bytes and other map fields remain unchanged; preserve a tested delivery copy separately from harnesses.

Public tests use original synthetic data, including an independently Ruby-produced map fixture. They cover fingerprints, shape/bounds/types, no-ops/duplicates, lower-byte and unknown-alias preservation, exact candidate postconditions, copy-only gating, one version advancement for mixed region/event edits, impact evidence, snapshot safety and complete rollback. Proprietary projects, raw native saves and test harnesses stay private.

Fourteen new tests passed with the complete 294-test runner. In private native copies, editor overlay and `Game_Map.region_id` agreed on three edited cells (7,63,1). An unchanged older save triggered the default project-version map reload while preserving player position, gold and health. A separate new-game harness invoked the actual engine `DataManager.save_game` once, then the Game process was fully closed and restarted; normal Continue/File1 loaded the same region Table and position without another map setup or save rewrite. This is native engine persistence evidence; it does not claim that UI-menu Save was exercised for this region fixture. The small seed has no encounter entries, so custom encounter/region consumers still require project-specific tests.
