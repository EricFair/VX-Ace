# Guarded blank-map append

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

## Optional size, tileset, parent and floor fill (v1.26)

The `append_blank_map` mutation also accepts optional `width`, `height` (17..500, 13..500), `tileset_id`, `parent_id` and `fill_floor`; the snapshot CLI takes `--width --height --tileset-id --parent-id --fill-floor` and reports `planned_map`. A size or tileset change, or `fill_floor`, rebuilds the tile Table (all zero; `fill_floor` puts the A5 tile `1536 + index` on layer 0 of every cell and is refused unless the tileset's A5 sheet is set and the tile is passable). Without these keys the operation is unchanged. Details, the A5 id range and examples are in [new areas](new-areas.md); it makes a walkable placeholder room and is not a level-design tool.

### Fresh-map mode (v1.26)

If `width`, `height` and `tileset_id` are all given, the template need not be inert: it is used only for the native field set, ivar order and audio-object shape, and the new map gets the editor's new-map defaults (no events, no encounters, `encounter_step` 30, no automatic audio, empty names/notes/backgrounds, scroll 0). Nothing from the template's content is copied, so a map with events, encounters, regions, notes or audio can be the template. The defaults were verified against an editor-created map; the table is in [new areas](new-areas.md#fresh-map-mode-any-map-can-be-the-template). Without all three keys, the strict inert-template rules of this document apply unchanged.

## Native verification and saves

Open the staged copy in VX Ace and inspect its new root tree entry, dimensions, tiles and empty events. Exercise an actual native transfer and ordinary collision-aware movement, old-save loading, native saving and a full process restart. Transfers are not authored by this operation; arrange a separate reviewed test/transfer on disposable copies.

System/version is intentionally unchanged because no existing map is changed. Default older saves on existing maps should not be forced to reconstruct them. Custom loaders, runtime-created maps and save hooks require separate review; a next static ID does not prove it is free in custom runtime state.

On a copy of a default editor project the full copy/postgate chain passed. The real engine loaded the unchanged older save, transferred to the new map, checked its dimensions, ground and zero events, walked on it with ordinary collision checks, saved, and loaded that save after a full Game-process restart. Only MapInfos and the new map files changed; the editor displayed the new root map and a blank event grid. A test driver invoked the transfer, movement and save APIs, so keyboard input is not established, nor is compatibility with arbitrary customized games.

No deletion, reparenting of existing maps, ID reuse, template logic cloning, transfer authoring in this operation, autotile painting (only the single-tile A5 floor fill is allowed) or general save migration is enabled; the new map size is optional within the editor's limits.
