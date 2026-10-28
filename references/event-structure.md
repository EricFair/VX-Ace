# Guarded event structure editing — v0.12

Later additions are separate, narrower workflows: [stationary dialogue-event creation](map-event-creation.md), [bound graphics on new dialogue events](character-event-graphics.md), and [one-time constant native rewards](one-time-event-rewards.md). [One guarded direct map transfer](direct-map-transfer.md) is a separate v1.4 operation. Transfer201 requires its full native source/event/destination context and a single blank-event insertion; it is not part of the unrestricted baseline command list. Reward commands125/126 require their complete native page/Items guards; the v0.12 baseline command list below does not authorize unguarded resource insertion.

Use the production copy patcher with `--backend python`. The low-level mutator is an internal implementation component, not a substitute for project-wide gates. Original-project writes remain prohibited. Close editors/playtests for the source snapshot; open only the resulting disposable copy for review.

## Supported scope

- Insert/delete root command units in map action/touch pages, non-triggered common events, and troop pages with Battle/Turn span.
- Insert map/troop pages by cloning an exact existing page of the same owner. A map clone is forced to Action Button; a troop clone to Battle span. Supply a complete explicit command list ending with code `0`, and explicitly enable a supported native condition.
- Delete a map/troop page while retaining at least one page. Page array and exact page/template hashes are required; explicitly acknowledge page priority changes. Highest-numbered valid map page wins; troop pages are evaluated in native order.
- New command subset: Show Text (`101` + `401`), comments (`108`/`408`), switches (`121`), map self switches (`123`), common-event calls (`117`), labels/jumps (`118`/`119`), waits (`230`, 1–3600 frames). New Ruby script commands and branch construction are refused.
- Existing messages/comments/scripts/routes/shops and balanced if/choice/loop/battle blocks are indivisible units for deletion or insertion boundaries. Unsupported or malformed nesting is refused conservatively. Final root terminators cannot be removed. Labels must remain unique and all jumps must resolve; an inserted batch must be internally valid too.

Autorun/parallel common/map events and Moment troop spans are refused. No blank-schema page creation, arbitrary native object replacement, database entry authoring, map/tile editing, or save-file mutation. Existing embedded script behavior and common-event recursion still require human/runtime review. A valid command structure cannot prove game logic terminates.

## Obtain exact preconditions

Use new external directories for every output. Pages are **one-based**; command indexes are **zero-based**. Indexes count actual native commands, including text continuations and the final terminator.

```powershell
python tools/vxace_project_validator.py PROJECT --output VALIDATION --backend python
python tools/vxace_project_reader.py PROJECT --output INDEX
python tools/vxace_event_snapshot.py PROJECT --map-id 1 --event-id 1 --page 1 --output SNAPSHOT
```

For common events use `--common-event-id 1`; for troops use `--troop-id 1 --page 1`. Select IDs from actual project evidence. The snapshot includes readable commands, legal boundaries, list/page hashes, page conditions and all page hashes. Hashes describe native serialization, not normalized JSON. Recompute after every preceding edit in a sequential specification, using a disposable staged result. Never guess or reuse a stale hash.

Example shape for inserting a message at a verified boundary (replace the hash and IDs with actual evidence):

```json
{
  "title": "Reviewed event message",
  "changes": [{
    "kind": "event",
    "locator": {"map_id": 1, "event_id": 1, "page": 1, "command_index": 0},
    "proposal": "Show the reviewed message before the existing first command",
    "mutation": {
      "action": "insert_commands",
      "expected_list_sha256": "REPLACE_WITH_SNAPSHOT_LIST_SHA256",
      "commands": [
        {"code": 101, "indent": 0, "parameters": ["", 0, 0, 2]},
        {"code": 401, "indent": 0, "parameters": ["Reviewed message"]}
      ]
    }
  }]
}
```

`delete_commands` uses `expected_list_sha256` and `count`; both start and end must be legal boundaries. `insert_page` uses a page-only locator, `expected_pages_sha256`, `expected_template_sha256`, `template_page`, `conditions`, `commands`, and `acknowledge_page_priority_change: true`. `delete_page` uses a page-only locator, `expected_pages_sha256`, `expected_page_sha256`, and the same acknowledgement. Unknown fields and locator overrides are refused.

Condition overrides: map `switch1_valid/id`, `switch2_valid/id`, `self_switch_valid/ch`; troop `turn_valid/a/b`, `switch_valid/id`. Only existing fields of the observed native types may be overridden. Other conditions/settings are inherited from the template: review the complete cloned page in the editor. Supplied switch/common-event references must exist in the fresh index. Limits: 500 inserted commands, 10,000 commands per resulting list, 32 pages.

## Plan, stage, review and play

```powershell
python tools/vxace_patch_planner.py INDEX --project PROJECT --spec patch.json --output PLAN
python tools/vxace_impact.py INDEX --spec patch.json --json impact.json --markdown impact.md
python tools/vxace_copy_patcher.py INDEX --project PROJECT --spec patch.json --copy NEW_COPY --audit NEW_AUDIT --backend python
```

Structural changes mandate re-indexing; `--no-reindex` is refused. The patcher checks source freshness/inventory, project-wide byte identity, every targeted file, an exact initial clone inventory, structural hashes and references. It applies the transaction only to a new copy, records before/after native snapshots and readable diffs, re-indexes, produces normalized/semantic diffs, validates the complete changed copy, then rechecks the source. A failed transaction removes the partial copy and reports any cleanup failure honestly.

Review `audit.json`, `audit.md`, `structural-impact.json`, `index-diff.md`, `semantic-diff.md`, `post-index/`, and `post-validation/`. Open the copy's `Game.rvproj2`; inspect all affected commands/pages/conditions and run relevant map interactions and Battle Test. Test New Game, save/load and an older save with affected state. Keep the original untouched and retain the reviewed spec/audit outside it.

## Old saves

VX Ace saves can cache the old map and event page. Every structural transaction automatically increments the verified native `System.version_id` in the copy, with the same byte gates. The default runtime then reloads the current map when an older save is loaded. Save files themselves are copied unchanged. A version mismatch can reset transient map event state, as native editor updates do; custom save/load scripts need separate review. This is not general save migration or proof of compatibility with customized runtimes.

Native editor/runtime evidence for this subset was recorded on disposable copies of an editor-created project (structural edits, old-save map reload and restart); it does not establish compatibility with arbitrary customized games.
