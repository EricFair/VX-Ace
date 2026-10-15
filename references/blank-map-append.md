# Guarded blank-map append — v1.2

Append one root-level map from a verified inert native template through the explicit Python disposable-copy workflow. The new map inherits the template's dimensions, tiles, tileset and permitted inert settings; its event hash is empty. Existing maps and map-tree entries are preserved. This is a bounded map creation operation, not a general map editor.

## Read-only evidence

Use a fresh external Project Reader index and the actual source project:

```powershell
python tools/vxace_maps.py EXTERNAL_INDEX --project PROJECT --template-map VERIFIED_TEMPLATE_ID --output NEW_EXTERNAL_SNAPSHOT
```

Read `map-append-snapshot.json`. The snapshot reports the next maximum static map ID, dimensions, inert placeholder count and four exact native guards. It grants no mutation permission. IDs and hashes must come from this project's current evidence; do not copy example IDs or invent values.

The native map files and MapInfos keys must agree exactly, with canonical filenames, no orphan/missing maps, unique orders/identities and an acyclic valid parent tree. The template must have exact supported native fields, non-looping geometry, no notes, encounters, named backgrounds, automatic audio or region IDs. Only blank stationary, unconditional, action-button placeholder events are accepted; they are discarded in the detached new map. Unknown fields or template logic refuse the operation. Selected native Tilesets identity and full-array hash are bound independently.

## Reviewed specification and copy

Create a single-change spec from the reviewed snapshot:

```json
{
  "title": "Append one reviewed blank map",
  "changes": [{
    "kind": "map_entry",
    "locator": {"template_map_id": 1},
    "proposal": "Append an empty root map using this project's verified inert template.",
    "mutation": {
      "action": "append_blank_map",
      "new_id": 2,
      "name": "New Clearing",
      "expected_infos_sha256": "REPLACE_FROM_SNAPSHOT",
      "expected_template_sha256": "REPLACE_FROM_SNAPSHOT",
      "expected_inventory_sha256": "REPLACE_FROM_SNAPSHOT",
      "expected_tilesets_sha256": "REPLACE_FROM_SNAPSHOT"
    }
  }]
}
```

The numeric IDs above are illustrative only. Choose the reported next maximum ID and a unique literal name of at most 100 characters. Review impact evidence for MapInfos, map loading, transfers, regions and save hooks, including dynamic IDs that static search cannot resolve.

```powershell
python tools/vxace_patch_planner.py EXTERNAL_INDEX --project PROJECT --spec reviewed-map.json --output NEW_EXTERNAL_PLAN
python tools/vxace_copy_patcher.py EXTERNAL_INDEX --project PROJECT --spec reviewed-map.json --copy NEW_DISPOSABLE_COPY --audit NEW_EXTERNAL_AUDIT --backend python
```

Keep mandatory re-indexing enabled. The copy chain requires project-wide validation plus immediate byte-identical MapInfos/template gates. It constructs the two native candidates together, creates the new map exclusively, preserves old entries/aliases and checks the entire copied-file inventory. Impact, re-indexing, semantic diff, project post-validation and new-map tile audit are mandatory. A failure deletes the entire staged copy and retains the audit. No standalone map writer or writable MCP is added.

## Native verification and saves

Open the staged copy in VX Ace and inspect its new root tree entry, dimensions, tiles and empty events. Exercise an actual native transfer and ordinary collision-aware movement, old-save loading, native saving and a full process restart. Transfers are not authored by this operation; arrange a separate reviewed test/transfer on disposable copies.

System/version is intentionally unchanged because no existing map is changed. Default older saves on existing maps should not be forced to reconstruct them. Custom loaders, runtime-created maps and save hooks require separate review; a next static ID does not prove it is free in custom runtime state.

On 16 October 2026, a private editor-produced default seed passed the full copy/postgate chain. Native VX Ace loaded the unchanged older save on map1 without an extra setup, transferred to new map2, checked 17×13 dimensions/ground and zero events, walked down onto the removed inert placeholder cell and back through ordinary `Game_Player.move_straight` collision checks, saved, then loaded that new-map save after full Game-process restart. Automated private hashes confirmed all prior Data files except MapInfos, System/version, old Save01 and restart Save02 preservation; pure candidate verification bound the new map/tree. A separate inspection copy displayed the new root map and blank event grid in the native editor. Input injection was unreliable, so a private authored driver invoked native transfer/movement/save APIs; this evidence does not establish keyboard input behavior.

All 420 automated tests passed locally, including 11 map candidate/copy/planner/refusal/rollback cases. Check the release commit's actual CI before claiming online success. Proprietary defaults, project data, saves, test drivers and raw reports are not distributed.

No resizing, deletion, reparenting, ID reuse, arbitrary dimensions, template logic cloning, transfer authoring, ground/autotile painting or general save migration is enabled. This limited default-project evidence does not establish compatibility with arbitrary customized games.
