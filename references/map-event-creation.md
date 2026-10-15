# Guarded stationary dialogue-event append — v0.26

This separate Python copy operation creates **one new event per selected existing map** from an exact native blank template. It does not create maps, delete/reuse events or copy arbitrary event logic. Only one stationary unconditional action-button page and one literal Show Text block are enabled. The base v0.26 schema keeps the graphic blank; v0.27 permits a [separately asset-bound character](character-event-graphics.md) on the new detached record. Existing template priority/movement flags are preserved, so review how the player can reach and activate the event.

## Capture actual template evidence

```powershell
python tools/vxace_map_events.py PROJECT_INDEX --project PROJECT --map MAP_ID --template-event EXISTING_ID --output NEW_PRIVATE_SNAPSHOT
```

The source/index must be fresh and complete. Native map dimensions/Table, event hash identity, selected exact Event/Page/Condition/Graphic/MoveRoute/command schemas and selected indexed template must agree. The template has exactly one empty command terminator, an empty route, no active conditions, stationary movement and an action-button trigger. Unknown selected fields, extra pages, logic, graphics or repeating triggers refuse creation. Existing unrelated events may contain custom logic and are preserved without cloning that logic.

Snapshot reports the exact native map/template Marshal hashes, next maximum event ID, occupied cells and template priority. It grants no mutation permission. Pick an unoccupied in-bounds cell and a unique literal name from reviewed project evidence. Append only at `max(existing IDs)+1`, at most999; never reuse holes. Runtime-created events and orphan self-switch/save IDs may still collide, requiring script/save review.

## Reviewed spec and copy

```python
mutation = {
    "action": "append_dialogue_event", "template_id": snapshot["template_id"],
    "new_id": snapshot["next_event_id"], "name": reviewed_unique_name,
    "x": reviewed_x, "y": reviewed_y, "text": reviewed_literal_lines,
    "expected_map_sha256": snapshot["map_sha256"],
    "expected_template_sha256": snapshot["template_sha256"]}
spec = {"changes": [{"kind": "map_event", "locator": {"map_id": captured_map_id},
                     "proposal": "Add the reviewed stationary village notice.", "mutation": mutation}]}
```

Names are1–100 characters; dialogue is1–4 lines of at most500 characters each, with some nonempty text. Control codes, newlines within a line and backslash escapes are refused; no dynamic actor/variable/icon/face references are introduced. The writer builds only fixed native codes101/401/0, with no face asset. No user-supplied command arrays or arbitrary field values are accepted.

```powershell
python tools/vxace_patch_planner.py PROJECT_INDEX --project PROJECT --spec PRIVATE_SPEC --output NEW_PLAN
python tools/vxace_copy_patcher.py PROJECT_INDEX --project PROJECT --spec PRIVATE_SPEC --copy NEW_DISPOSABLE_COPY --audit NEW_AUDIT --backend python
```

Use one append per map and no other change to that same map in one transaction. Explicit Python backend and re-indexing are mandatory. Complete project and immediate target byte gates, native/indexed template verification, exact full-map/template preconditions, bounded consumer impact, candidate preservation, semantic diff and full post-project validation remain required. Failure removes the staged copy and retains the audit. Original files are never written.

The native event hash is detached before append. Old entries/order/serialized bytes and all unrelated map fields, Table data and unknown aliases are verified unchanged. The new record must exactly equal the approved detached native template with only ID/name/coordinates/dialogue replaced. The copy's System.version advances once, allowing default old-save loading to reconstruct edited-map events. Custom map/save hooks and runtime event ownership remain review concerns.

## Acceptance evidence

Public tests use an authored Ruby schema fixture and synthetic data. Fourteen new tests cover exact template/identity/position/schema refusal, candidate preservation, full copy/version/impact/postgates, stale evidence and rollback.

On a private native blank-seed copy, VX Ace displayed the appended ID002/name, one fixed action-button page and both literal dialogue lines. Canceling inspection kept the map bytes unchanged. An unchanged older save reconstructed the map once through the version change, found the new event at(9,6) and retained the player at(8,6). Facing right and pressing the native action button displayed both lines; dismissing the message completed the interpreter and wrote one new native save. A different Game process reloaded the new event and the driver's saved completion state without extra map setup or save rewrites. Existing events, other map fields and other Data files were unchanged. These results establish the inspected fixture's behavior, not arbitrary custom event/save scripts.

For each actual project, inspect ID/coordinates/priority/commands in VX Ace and test action-button access, saving and restart. Preserve source/RTP/original hashes and keep proprietary fixtures/reports private.
