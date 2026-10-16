# One guarded direct map transfer — v1.4

Insert one native Transfer Player command201 into an existing exact blank, one-page, stationary, unconditional action-button map event. The destination must be a different verified inert static map with no events. This narrow operation connects a blank map to gameplay through the existing Python disposable-copy workflow.

## Fresh read-only evidence

Choose actual IDs/coordinates from the current project and fresh external index:

```powershell
python tools/vxace_transfers.py EXTERNAL_INDEX --project PROJECT --map SOURCE_MAP_ID --event BLANK_EVENT_ID --destination DESTINATION_MAP_ID --x REVIEWED_X --y REVIEWED_Y --output NEW_EXTERNAL_SNAPSHOT
```

Optional `--direction` accepts0 retain,2 down,4 left,6 right,8 up; default2. Optional `--fade` accepts0 normal,1 white,2 none; default0. These map to native editor choices and default interpreter/scene behavior. Parameters must be literal integers, never booleans or variable designation.

Read `transfer-snapshot.json`: exact blank list hash, one command row, six native guards, actual destination bounds and static tile evidence. The snapshot checks complete native/indexed source map, destination map, MapInfos and Tilesets projections. It authorizes no writes. Static tile observations cannot establish runtime reachability, asset decoding, vehicles or custom movement/transfer hooks.

The source event must satisfy the existing strict blank-template schema, including one empty native command list, no conditions, fixed movement and blank graphics. The destination uses the strict inert-map subset from [blank-map append](blank-map-append.md): canonical tree/file inventory agreement, supported schemas, no logic/events, encounters, notes, automatic audio/backgrounds, looping or region IDs. Full source/event/destination/tree/inventory/tileset hashes bind actual native context independently of indexed observations.

## Reviewed single-change specification

Copy values from the current snapshot into this shape; illustrative IDs/coordinates below are not defaults for arbitrary projects:

```json
{
  "changes": [{
    "kind": "event",
    "locator": {"map_id": 1, "event_id": 1, "page": 1, "command_index": 0},
    "proposal": "One reviewed direct transfer from the verified blank event.",
    "mutation": {
      "action": "insert_commands",
      "expected_list_sha256": "REPLACE_FROM_SNAPSHOT",
      "commands": [{"code": 201, "indent": 0, "parameters": [0, 2, 8, 6, 2, 0]}],
      "transfer_guard": {
        "expected_source_sha256": "REPLACE_FROM_SNAPSHOT",
        "expected_event_sha256": "REPLACE_FROM_SNAPSHOT",
        "expected_destination_sha256": "REPLACE_FROM_SNAPSHOT",
        "expected_infos_sha256": "REPLACE_FROM_SNAPSHOT",
        "expected_inventory_sha256": "REPLACE_FROM_SNAPSHOT",
        "expected_tilesets_sha256": "REPLACE_FROM_SNAPSHOT"
      }
    }
  }]
}
```

Review high-risk impact evidence for interpreter, setup, transfer, loader and save consumers, then stage:

```powershell
python tools/vxace_patch_planner.py EXTERNAL_INDEX --project PROJECT --spec reviewed-transfer.json --output NEW_EXTERNAL_PLAN
python tools/vxace_copy_patcher.py EXTERNAL_INDEX --project PROJECT --spec reviewed-transfer.json --copy NEW_DISPOSABLE_COPY --audit NEW_EXTERNAL_AUDIT --backend python
```

Exactly one reviewed change is allowed. The patcher adds the native System/version update, requires project-wide and immediate target byte gates, verifies the exact candidate, re-indexes, reviews semantic changes, post-validates and audits both source/destination map tiles. It binds the complete final copied-file inventory to the actual approved map/System candidate hashes and rechecks destination/tree/tileset bytes after postgates. Any failure removes the staged copy and preserves the audit. Do not disable re-indexing or call the low-level mutator as a gate bypass.

## Native tests and evidence

Inspect the staged event in VX Ace. Test older-save source-map reconstruction, actual event execution, destination rendering, ordinary collision-aware movement, native saving and a full Game-process restart. The System/version update causes default old-save loading to rebuild the edited source map; custom loaders/save hooks need separate review. The operation does not edit saves or guarantee that a landing cell has an escape route.

On16 October2026, a private default-project copy passed all staging/postgates. Its older Save01 reconstructed the source map once and gained exactly the201 command; the native event then executed the actual default interpreter command once and transferred to map2 at8:6, facing down with normal fade. Native assertions checked17×13, grass, zero destination events and setup counts. Ordinary native movement down/up, Save03 and full-process restart passed. Both prior saves, the new restart save, destination map/tree/tilesets and all other Data were hash-preserved; only the exact source-map command and System/version changed. Separate editor inspection showed `Transfer Player: [002:Native Clearing] (008,006), Down` on the one unconditional action-button page. A private driver started the event to avoid unreliable short key injection; it did not reserve or simulate the transfer. This does not establish keyboard interaction behavior or arbitrary customized-project compatibility.

Ten focused independent Ruby fixture/candidate/copy/planner/refusal/rollback tests passed, including strict locators, all native direction/fade parameter combinations, stale native/indexed bindings, unsupported sources/targets, candidate preservation and late-copy tampering cleanup. Actual runtime evidence covers the down/normal combination above. Check the release commit's full-suite and CI result before claiming online success. Proprietary defaults/project/RTP/saves/drivers/raw reports stay private.

Variable transfers, same-map transfers, multiple/mixed command batches, nonblank/conditioned/touch/repeating/common/troop event authoring, destination logic, arbitrary map editing and general save migration remain deferred. Existing broader parameter-editing behavior is unchanged; this reference authorizes only the new guarded insertion subset.
