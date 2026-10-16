# One guarded editor/tree map name — v1.6

`map_label` changes one existing `RPG::MapInfo.name` in `Data/MapInfos.rvdata2`. This is the editor/tree label. The player-visible `RPG::Map.display_name` is a separate [guarded operation](map-display-names.md). IDs, parent/order/scroll metadata, all other entries/string aliases, every map file, System/version, resources and prior saves stay unchanged.

## Capture exact native evidence

Generate a fresh complete index, then run:

```powershell
python tools/vxace_map_labels.py PROJECT_INDEX --project PROJECT --map MAP_ID --output NEW_EXTERNAL_SNAPSHOT
```

The read-only snapshot requires a byte-identical native MapInfos no-op round trip, supported bounded native MapInfo/table schema, valid unique IDs/orders/owners and acyclic existing parents. Canonical map files and native tree IDs must agree exactly. It binds the complete native tree, selected entry/current name and full map-file inventory; the indexed tree must agree with actual native data. Unknown fields/encodings, missing/orphan/case-aliased maps, stale/incomplete/linked/changed inputs and contained/existing outputs refuse.

Construct one reviewed change from `map-label-snapshot.json`:

```python
spec = {"changes": [{
    "kind": "map_label",
    "locator": {"map_id": snapshot["map_id"]},
    "proposal": "Rename the reviewed map in the editor tree.",
    "mutation": {
        "action": "set_tree_name",
        **snapshot["guard"],
        "value": "Oakfall Forest"
    }
}]}
```

Keep all four guard fields: `expected_infos_sha256`, `expected_entry_sha256`, `expected_inventory_sha256` and `expected_name`. Both old and new selected labels must be plain single-line UTF-8 text, at most64 characters/256 bytes, without control/format characters or surrounding whitespace. No-op changes refuse. Labels are not IDs: duplicate labels are valid, and the exact map ID selects the target. The new native string is detached so shared old strings on other entries remain unchanged. Legacy code pages are never guessed.

## Review and stage a disposable copy

```powershell
python tools/vxace_patch_planner.py PROJECT_INDEX --project PROJECT --spec PRIVATE_SPEC --output NEW_PLAN
python tools/vxace_copy_patcher.py PROJECT_INDEX --project PROJECT --spec PRIVATE_SPEC --copy NEW_DISPOSABLE_COPY --audit NEW_AUDIT --backend python
```

Use exactly one label change and no other user mutation. The explicit Python backend and post-copy re-indexing are mandatory. The low-level worker requires the actual canonical native MapInfos path, reads adjacent map files and verifies the supplied tree/context against that source. Source/index freshness, complete selected-backend project and immediate target byte gates, exact reconstructed candidate preservation, impact, re-index/semantic comparison, post-project validation, selected-map audit and final complete copied-file hashes are required. Only the approved MapInfos candidate may differ. Failure removes the entire copy and retains its audit; originals and saves are never edited.

System/version does not advance because no map data changes. Default `DataManager` reloads MapInfos on process startup; an existing save at the same native project version does not need another map setup for this label edit. Already stale project versions or custom loaders/name caches/save hooks can behave differently and require review. Bounded literal mentions of `$data_mapinfos`, `MapInfo`, `DataManager` and the old label are dependency evidence, not proof that no hidden name-based consumer exists. Inspect the concrete field audit; a Codex semantic diff can remain empty when its gameplay classifications/display labels are unaffected.

## Verification evidence and limits

Twelve independent authored Ruby fixture tests cover child metadata/order, shared strings/duplicate labels, exact native guards/schema/inventory, low-level context, planner, copy/refusal and rollback. The complete465-test suite passed locally.

On disposable native copies, an existing save from before the label edit loaded with the new startup tree label “Oakfall Forêt,” the same player-visible “Oakfall Café,” unchanged position and no additional map setup. Ordinary collision-aware left/right movement, a new native Save03 and a full Game-process restart passed. All three save hashes stayed unchanged across restart, and every map file/System/version/other Data file matched the source exactly. Source/RTP and20 recorded original-project hashes were preserved.

The actual editor displayed “Oakfall Forêt” in the tree and Name field while Display Name remained “Oakfall Café,” with the same Field tileset and17×13 map. Properties were cancelled without saving; all33 separate inspection-copy files remained unchanged. This is limited evidence on a small default-project fixture, not a guarantee about custom name consumers/caches or every font. Proprietary projects, engine scripts, RTP, saves, private observers and raw reports stay private.

No resize/delete/reparent/ID reuse, other map properties, display-name change or general raw-field writer is enabled by this operation.
