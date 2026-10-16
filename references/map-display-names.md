# One guarded existing-map display name — v1.5

This operation changes only the native `RPG::Map.display_name` string, which the default map-name window displays. It does not rename the map in the editor/tree (`MapInfos.name`), change its ID, or modify other properties, tiles, events, encounters or resources. Custom map-name windows, dynamic maps and save hooks need project-specific review.

## Capture exact evidence

Generate a fresh complete Project Reader index, then run:

```powershell
python tools/vxace_map_names.py PROJECT_INDEX --project PROJECT --map MAP_ID --output NEW_EXTERNAL_SNAPSHOT
```

The read-only snapshot requires a byte-identical native no-op load/dump, canonical existing map ID1..999, the supported native Map field set and exact native/indexed normalized agreement. It reports the current display name, whole-map SHA-256 and dimensions. Unknown Map fields, legacy string encoding tags, stale/incomplete/linked/changed inputs and contained/existing outputs refuse. Reports and indexes stay outside the source project.

Construct one reviewed change from `map-name-snapshot.json`:

```python
spec = {"changes": [{
    "kind": "map_name",
    "locator": {"map_id": snapshot["map_id"]},
    "proposal": "Show the reviewed village name.",
    "mutation": {
        "action": "set_display_name",
        "expected_map_sha256": snapshot["map_sha256"],
        "expected_display_name": snapshot["display_name"],
        "value": "Oakfall Village"
    }
}]}
```

Both old and new names must be plain single-line UTF-8 text, at most64 characters/256 bytes, without control/format characters or surrounding whitespace. Empty clears the displayed name; a no-op refuses. This operation creates a detached UTF-8 native string so shared old string aliases remain unchanged. It never guesses a code page, interpolates Ruby or creates event/script logic.

## Review and stage a copy

```powershell
python tools/vxace_patch_planner.py PROJECT_INDEX --project PROJECT --spec PRIVATE_SPEC --output NEW_PLAN
python tools/vxace_copy_patcher.py PROJECT_INDEX --project PROJECT --spec PRIVATE_SPEC --copy NEW_DISPOSABLE_COPY --audit NEW_AUDIT --backend python
```

Use exactly one display-name change and no other user mutation in the transaction. The explicit Python backend and post-copy re-indexing are mandatory. The low-level worker also requires the actual canonical native map path and verifies it agrees with the supplied object before applying. Source/index freshness, complete selected-backend project gates and immediate native map/System byte gates run before staging. The candidate must equal the independently reconstructed approved map with only the detached name string replaced; every other native field/alias is preserved.

The copy's System.version advances once so default older-save loading reloads the changed map. Impact reports bounded literal mentions of `display_name`, `Window_MapName`, `Game_Map` and `DataManager`; these are review evidence, not proof that no hidden consumer exists. Re-indexing, semantic diff, post-project validation, selected-map tile audit and final complete copied-file hashes are required. Only the target map and exact native version update may differ from the source. Failure removes the whole disposable copy and retains the failure audit. Original projects and saves are never edited.

## Native review and limits

Inspect the actual Display Name field in a separate disposable editor copy and observe the native map-name window. Test an older save, actual map reload, ordinary collision-aware movement, a new native save and a complete Game-process restart. Confirm original/source/native asset bytes and previous saves remain unchanged. Empty names can intentionally suppress the default name window; localized/custom windows and fonts still need native testing. A static string/serialization check cannot prove font coverage or the behavior of custom hooks.

This finite capability does not enable a general map-property editor, tree-name changes, resize/delete/reparent/ID reuse or other map/event authoring.

## Verification evidence

Eleven independent authored Ruby fixture tests and the complete453-test local suite passed. A private observer on a disposable default-project copy saved the blank-name baseline, loaded that older save after the guarded name edit and observed exactly one additional map setup. The actual native map-name window rendered the UTF-8 name “Oakfall Café”; the observer reopened the unchanged native window through PageUp for inspection. Ordinary collision-aware movement left/right, native saving and full Game-process restart passed, preserving the name/position without another setup or save rewrite. Every other Data file, the previous save, baseline/source and selected RTP asset stayed unchanged;20 recorded original-project hashes matched. The first fixture's water blocked movement, so a new disposable baseline used the already released guarded upper painter for two verified passable cells. The movement assertion was retained.

The actual native editor opened a separate disposable inspection copy and displayed “Oakfall Café” in Display Name while Name/tree stayed MAP001, Field tileset and17×13 dimensions remained intact. Properties were cancelled without saving, and all27 inspection-copy file hashes stayed unchanged. Proprietary project/scripts/RTP/saves, private observers and raw evidence stay outside the public repository.
