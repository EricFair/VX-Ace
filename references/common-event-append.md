# Guarded common event append — v1.21

`append_common_event` appends **one new `RPG::CommonEvent`** to `Data/CommonEvents.rvdata2` at the next id. The command list uses the same bounded command language as [staged events](staged-events.md) (text, switches, variables, choices, if/else, battle, party, common event call, gold, item, weapon, armor, transfer, wait, and since v1.25 a player move route; `erase_event` and `this` routes are refused here); the language is reused from `tools/vxace_staged_commands.py`, not copied. The new event is either **call-only** (run by a Call Common Event command or an item/skill effect 44) or a **parallel process** gated by a switch. Autorun is refused: it has no termination proof.

It is a copy-only operation on its own change kind, `common_event`. Python backend, mandatory re-indexing, one common event per transaction (the transaction holds exactly one change); the Ruby backend and `--no-reindex` are refused. Only `CommonEvents.rvdata2` changes. System and every referenced database are read only.

## Snapshot

```powershell
python tools/vxace_common_event_append.py PROJECT_INDEX --project PROJECT --output NEW_PRIVATE_SNAPSHOT [--transfer-map MAP_ID ...]
```

Read-only, needs a fresh complete index. It reports `next_id` (the exact next array slot), `existing_entries`, `append_slot_supported` (the array may hold ids up to 999), `empty_slot_ids` (the editor's blank placeholder slots, see below), the existing named events, `common_events_sha256` (the target array), `system_sha256`, `switch_count`, `variable_count`, `switch_names`, `variable_names` (id 1 first), and the hashes and counts of every database a command may reference (`troops_sha256`, `actors_sha256`, `items_sha256`, `mapinfos_sha256`; null when absent). `--transfer-map N` (repeatable) adds `destination_maps` with each map's `sha256`, `width` and `height`. The snapshot grants no mutation permission.

## Spec

```json
{"changes": [{"kind": "common_event", "locator": {"table": "common_events"}, "proposal": "Inn stay for 50 gold.",
  "mutation": {"action": "append_common_event", "new_id": 11, "name": "Inn Stay", "trigger": "none",
    "expected_common_events_sha256": "...", "expected_system_sha256": "...",
    "commands": [{"text": ["Welcome to the inn."]}, {"gold": -50}]}}]}
```

The locator is exactly `{"table": "common_events"}`. The mutation has exactly these keys (anything else is refused):

| Key | Rules |
| --- | --- |
| `action` | `"append_common_event"` |
| `new_id` | The next array slot (`len(array)`), at most 999. Holes and the editor's blank placeholder slots are never reused |
| `name` | 1..100 literal characters (no control characters, no backslash), unique among the existing common event names. Blank placeholder names do not count |
| `trigger` | `"none"` (call-only, stored `0`) or `"parallel"` (stored `2`). `"autorun"`, `1` and anything else is refused |
| `switch_id` | **Required for `parallel`, forbidden for `none`.** An integer `1..len(System.switches)-1` |
| `commands` | The staged command list, see below |
| `expected_common_events_sha256` | SHA-256 of the Marshal dump of the current CommonEvents array (always required) |
| `expected_system_sha256` | SHA-256 of the Marshal dump of `Data/System.rvdata2` (always required; the switch and variable ids are checked against it) |
| `expected_<db>_sha256` ... | Only for the databases the commands use, see "Referenced databases" |

### Fields written

The new object is built directly (there is no template) in the layout the VX Ace editor saves. Checked against an editor-saved project with ten common events, `RPG::CommonEvent` has exactly five instance variables, in this order:

| Order | Ivar | Type | Written value |
| --- | --- | --- | --- |
| 1 | `@trigger` | Integer | `0` for `none`, `2` for `parallel` |
| 2 | `@name` | String (UTF-8 flagged) | the spec `name` |
| 3 | `@switch_id` | Integer | the spec `switch_id` for `parallel`; **`1` for `none`**, exactly what the editor stores for a call-only event |
| 4 | `@list` | Array of `RPG::EventCommand` | the generated commands plus the final terminator `0` |
| 5 | `@id` | Integer | `new_id` |

Each `RPG::EventCommand` has its ivars in the editor order `@indent`, `@code`, `@parameters`. The editor stores unused slots as **empty common events** (name `""`, trigger `0`, switch id `1`, list with only the terminator), not as `nil`. A project with such placeholder slots appends **after** them, at the next array slot; a placeholder is never reused. Existing entries must carry exactly this field set with their slot id, or the append is refused.

### Trigger rules

- **`none`**: no `switch_id` key. The stored switch id is `1`; the engine ignores it for a call-only event.
- **`parallel`**: `switch_id` is required and must be a valid System switch. The commands must contain **at least one `wait`** (anywhere in the list, including a branch). The impact report warns when every wait is inside a branch and when no command turns the trigger switch OFF.
- **`autorun`** (1) is refused: a common event with an autorun trigger starts as soon as its switch is ON and, unlike a map event, has no terminating page selection to end it.

### Commands

`commands` is the staged command list: 1..40 operations, nesting depth 4, 40 operations per nested list and at most 200 generated native commands. The operation tables, condition forms and generated native commands are in [staged events](staged-events.md#page-fields); they are the same here. Two rules are specific to common events:

- **Self switches are refused.** `set_self_switch` and the `self_switch` condition need an owning map event, which a common event does not have.
- **`erase_event` is refused.** `214` erases the event that runs it (`Game_Interpreter#command_214` does nothing without an event id), and a common event has no owning event.
- **`move_route` with `"target": "this"` is refused** for the same reason. `"target": "player"` is allowed (`205 [-1, RPG::MoveRoute]` plus the `505` lines, see [Move routes](staged-events.md#move-routes)); `repeat: true` with `wait: true` is refused everywhere because it would stall the interpreter forever.
- **No call to the new id.** A `common_event` command whose id equals `new_id` is refused (direct recursion). Calls to other existing common events are allowed and are checked against the **pre-append** array.

### Referenced databases

The same per-database hashes as staged events (see [Referenced databases](staged-events.md#referenced-databases-v119)). Only the files the commands use appear (an unneeded hash field is refused as an unknown key; a needed one that is missing or stale refuses):

| Used by | Required mutation fields |
| --- | --- |
| `battle` | `expected_troops_sha256` |
| `party` | `expected_actors_sha256` |
| `item`, `has_item` | `expected_items_sha256` |
| `transfer` | `expected_mapinfos_sha256`, `expected_destination_maps_sha256` (`{"<map_id>": sha}`) |
| `common_event` | no extra field: the target array's own `expected_common_events_sha256` binds the pre-append array that the call is checked against |

`expected_common_events_sha256` and `expected_system_sha256` are always required. System ids used by any command or by `switch_id` must be `1..len-1` of the native `System.switches` / `System.variables`.

## Examples

### Inn

Choices Yes/No; Yes checks 50 gold, takes it, waits and shows a message.

```json
{"action": "append_common_event", "new_id": 11, "name": "Inn Stay", "trigger": "none", "commands": [
  {"choices": ["Yes", "No"], "cancel": 1, "branches": [
    [{"if": {"gold_at_least": 50}, "then": [{"gold": -50}, {"wait": 30}, {"text": ["You feel rested."]}],
      "else": [{"text": ["Not enough gold."]}]}],
    [{"text": ["Come again."]}]]}]}
```
Generated: `102 [["Yes","No"],2]`, `402 [0,"Yes"]`, `111 [7,50,0]`, `125 [1,0,50]`, `230 [30]`, `101`/`401`, `411`, `101`/`401`, `412`, `402 [1,"No"]`, `101`/`401`, `404`, then the terminator. No extra hash fields are needed (no database is referenced). The impact report notes the gold removal; the `gold_at_least` guard answers it.

### Reward chain called from an NPC

Two call-only common events, the second calling the first, then an NPC that calls the second. In a recipe the NPC refers to the new ids with `from_step`:

```json
{"steps": [
  {"type": "append_common_event", "name": "Gold Reward", "trigger": "none", "commands": [{"text": ["A purse!"]}, {"gold": 25}]},
  {"type": "append_common_event", "name": "Reward Chain", "trigger": "none", "commands": [{"common_event": {"from_step": 1}}, {"text": ["Well done."]}, {"set_switch": 1, "value": true}]},
  {"type": "append_blank_event", "map_id": 1, "donor_event": 1, "x": 5, "y": 5},
  {"type": "append_staged_event", "map_id": 1, "template_event": {"from_step": 3}, "x": 8, "y": 8, "name": "Reward NPC",
   "pages": [{"condition": {}, "commands": [{"text": ["Take this."]}, {"common_event": {"from_step": 2}}]}]}]}
```
As a plain spec, the second event's `commands` contain `{"common_event": 11}` and the mutation carries no extra hash (its own `expected_common_events_sha256` already binds the array that holds event 11).

### Parallel timer

Waits 60 frames and adds 1 to a variable, gated by a switch.

```json
{"action": "append_common_event", "new_id": 12, "name": "Tick Counter", "trigger": "parallel", "switch_id": 5, "commands": [
  {"wait": 60}, {"set_variable": 3, "op": "add", "value": 1}]}
```
Generated: `230 [60]`, `122 [3,3,1,0,1]`, terminator; stored `@trigger` 2, `@switch_id` 5. Nothing stops this event except turning switch 5 OFF. A map event must set switch 5 ON to start it and OFF to stop it; to stop it from inside, add `{"if": {"variable": 3, "op": ">=", "value": 10}, "then": [{"set_switch": 5, "value": false}]}` as a command. The impact report warns that it repeats every frame while the switch is ON, and again when no command turns the switch OFF.

## Verification and audit

Candidate verification requires: the old array bytes identical, exactly one appended entry, the new entry equal to the factory result for the approved spec (so field set, ivar order, types, id, trigger, switch id, name and every command are exact), the generated list passing `vxace_event_structure.validate_list` (balanced blocks, matching indent, one terminator), and every other file in the copy byte-identical. System's `version_id` is **not** advanced: common events are part of the database loaded at start, not saved data (the existing database appends leave it alone too). Referenced databases and destination maps stay byte-identical.

The audit records `action`, `new_id`, `name`, `trigger`, the stored trigger and switch id, the field order, the spec commands, the generated native rows (`native_rows`), the operation and native command counts, `expected_common_events_sha256`, `expected_system_sha256`, the `reference_hashes` of every referenced database, and the preservation flags. The diff shows the generated rows.

## Impact report

`structural-impact.json` / `impact.md` list for the common event: the target (id, name, trigger, stored switch id), the commands in plain language (`common_event.summary`, for example `Take 50 gold`, `Turn switch 1 "QuestStarted" ON`, `Call common event 1 "Advance Quest"`), the called common events by name, and `warnings` for:

- the parallel trigger (repeats every frame; no command turns the trigger switch OFF; every wait inside a branch);
- battles, transfers and gold removal;
- every call to another common event, naming it;
- unnamed switches and variables (empty name in System), including the trigger switch;
- an **existing common event call cycle** in the project, found with the same bounded graph as the [cycle diagnostics](common-event-cycles.md) on the indexed common events; a call from the new event into an existing cycle; existing common events that already contain a Call Common Event for the new id (an absent target today, live after the append); and a cycle the new event would close.

The call graph covers direct Call Common Event commands of common events only; map and troop events that already call the new id, and scripts, are not scanned.

## Recipe step

```json
{"type": "append_common_event", "name": "Tick Counter", "trigger": "parallel", "switch_id": 5, "commands": [ ... ]}
```

Keys: `name`, `trigger`, `commands`, and `switch_id` for `parallel` only. Inside `commands`, a `common_event` id may be `{"from_step": k}` (an earlier `append_common_event` step), a `battle` troop id may be `{"from_step": k}` (an `append_entry` on `troops`) and an `item` / `has_item` id may be `{"from_step": k}` (an `append_key_item` step or an `append_entry` on `items`). A `common_event` id in an `append_staged_event` page and the `data_id` of an item or skill `effects` row with code 44 may also be `{"from_step": k}` pointing at an `append_common_event` step. All hashes come only from the step's snapshot (the runner passes `--transfer-map` for every transfer destination); a recipe cannot supply them. The step creates the next common event id, cross-checked against the audit. See [recipes](recipes.md).

## Limits

- No autorun, no self switches, no erase_event, no event move routes (player routes only), no scripts, loops, labels, jumps, shops, variable operands or variable transfer destinations; the staged command language limits apply (depth 4, 40 operations per list, 200 generated commands).
- A parallel process has no termination proof. It needs a `wait` and a switch, but whether it ever stops depends on when the switch is turned OFF.
- Nothing calls the new event: wire it from an event, an item/skill effect 44, another common event or a script. The append never edits an existing event, item, skill or map.
- A new static id can collide with runtime-created or custom-indexed common events, and existing events that already call the id will start running it (the impact report names those common events).
- One common event per transaction; at most 999 entries. Placeholder slots left by the editor stay empty; the new event goes after them.
- Text is plain literal text; switch and variable semantics are not simulated. Check runtime behavior in the game.

## Native evidence (v1.21)

A six-step recipe on an editor-created project passed all postgates, and the original project was unchanged. The steps were:
- three common events: an Inn with a choice and a gold check, a parallel Timer gated by switch 5, and a Cheer event that gives gold;
- a Cheer Potion with effect 44 pointing at Cheer through `from_step`;
- a blank event and an Innkeeper page calling the Inn through `from_step`.

In a real-engine smoke run:
- **Inn with 100 gold:** choosing Yes charged 50 gold.
- **Inn with 15 gold:** the `gold_at_least` else branch ran and no gold was taken.
- **Timer:** it stayed idle while switch 5 was OFF. Once the switch was ON it added 5 over about 330 frames, and it stopped when the switch went OFF.
- **Cheer Potion:** using it reserved and ran Cheer (+25 gold).

An existing save loaded with the new common events and the Innkeeper. Effect 44 only fires through the engine's `use_item` path (menu or battle use), not through a direct `item_apply`.
