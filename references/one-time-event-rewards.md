# Guarded one-time native map-event rewards — v1.0

This extension enables one constant positive gold grant and/or one constant positive item grant in a **blank lower map-event page**, followed by its reviewed self switch. It does not enable variable operands, removal, equipment grants, branches/scripts, common/troop scopes or a general event DSL.

## Establish the native one-time guard first

The existing event must have exactly two stationary action-button pages. Page1 is unconditional with only its native final command terminator. Higher page2 has only one enabled condition: a native self switch, A–D. Its command list contains only bounded literal Show Text/comments and the terminator, so that page cannot reset the gate or grant another reward itself. Unknown/missing selected Page/Condition schemas, other conditions/triggers, extra pages, nonblank lower logic or executable follow-up logic refuse insertion.

If needed, stage the higher page first through [guarded page insertion](event-structure.md), on a separate copy, using the inspected exact native template/conditions and fresh hashes. Re-index that staged result before planning rewards. Do not combine page construction with the reward insertion transaction or assume an existing self-switch meaning.

```powershell
python tools/vxace_event_rewards.py PROJECT_INDEX --project PROJECT --map MAP_ID --event EVENT_ID --item ACTUAL_ITEM_ID --output NEW_PRIVATE_SNAPSHOT
```

Omit `--item` for gold-only rewards. The snapshot independently reads the native selected map/pages and optional Items file, checks selected indexed identities/conditions/command lists/name and reports the exact blank-list/pages/full Items hashes and observed self switch. Snapshot output is read-only, external and not mutation permission.

## Concrete command spec

Keep the snapshot's exact guard. A reviewed example shape is:

```python
mutation = {
    "action": "insert_commands",
    "expected_list_sha256": snapshot["expected_list_sha256"],
    "reward_guard": snapshot["reward_guard"],
    "commands": [
        {"code": 101, "indent": 0, "parameters": ["", 0, 0, 2]},
        {"code": 401, "indent": 0, "parameters": [reviewed_literal_message]},
        {"code": 125, "indent": 0, "parameters": [0, 0, reviewed_gold]},
        {"code": 126, "indent": 0, "parameters": [captured_item_id, 0, 0, reviewed_quantity]},
        {"code": 123, "indent": 0,
         "parameters": [snapshot["reward_guard"]["self_switch"], 0]}]}
spec = {"changes": [{"kind": "event",
    "locator": {"map_id": captured_map_id, "event_id": captured_event_id,
                "page": 1, "command_index": 0},
    "proposal": "Grant the reviewed one-time native reward.", "mutation": mutation}]}
```

Use at most one125 and one126, at root indent0. Gold is1–99,999,999; item quantity1–99; item ID comes from the actual native named `RPG::Item` at that array slot. Both operation and operand-type are0 (add, constant). No booleans, zero, negative/removal, variables or other command types are accepted. Optional literal message/comment rows are bounded and asset-free, without escapes/control codes. The last inserted command must enable the exact higher-page self switch. The original native final terminator remains intact.

The guard has exactly `expected_pages_sha256`, `self_switch`, `expected_items_sha256`. An item grant binds the complete actual native Items array; gold-only uses an explicit null Items hash. Missing/ambiguous native item identities or stale full-array/page hashes refuse. Default inventory/gold caps can truncate grants **while the self switch still completes the reward**: review relevant party state, custom gain/cap hooks and reward design before use.

## Stage and verify

```powershell
python tools/vxace_patch_planner.py PROJECT_INDEX --project PROJECT --spec PRIVATE_SPEC --output NEW_PLAN
python tools/vxace_copy_patcher.py PROJECT_INDEX --project PROJECT --spec PRIVATE_SPEC --copy NEW_DISPOSABLE_COPY --audit NEW_AUDIT --backend python
```

Use a single reward change in its own transaction. Explicit Python backend, fresh complete source/index, all project/target byte gates, actual native map/Items context, one-time page/command checks, impact, exact candidate reconstruction, version advance, re-index/semantic/full post-validation and final Items recheck remain mandatory. Low-level writes require an actual canonical native map source path. A candidate must match exactly the approved structural change, preserving all other map fields, pages/events and native bytes. Failures remove the staged copy and retain the failure audit. Originals, Items and saves are never edited by the writer.

The gate proves the inspected default-engine page arrangement, not global game logic. Other events/scripts can pre-enable or reset the self switch; existing saves can already contain it; custom page/gain/save hooks can alter behavior. Impact reports bounded literal consumers and capacity/state limitations, never executes scripts and grants no mutation authority. Later edits require a fresh review and native regression testing.

## Acceptance evidence

Twelve new authored Ruby/synthetic tests cover native rewards, candidate preservation, unsafe operands/scopes/guards, actual Items/index disagreement, gold-only binding, read-only planning, complete copy/version/postgates and final-context-change rollback. Native VX Ace verification on 15 October 2026 loaded an unchanged older save, reloaded the two-page map once, granted 25 gold and one actual Potion, selected the higher self-switch A page and displayed Already rewarded on repeat interaction without another grant. The native menus showed 25 gold and Potion quantity1. A native save and full Game-process restart retained gold, item and self switch without another map setup or rewriting either save. Exact candidate verification preserved all other map fields; Items, other unrelated Data files and source remained unchanged. All 400 automated tests passed locally. This is bounded default-seed evidence, not arbitrary custom gain/save compatibility. Keep proprietary projects/default scripts/saves/raw reports private.
