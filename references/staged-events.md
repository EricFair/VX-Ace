# Guarded quest-stage event pages — v1.18, nested commands v1.19

`append_staged_event` is a third action on the existing `map_event` change kind. It creates **one new event** on an existing map from an exact blank template event (the same predicate as [`append_dialogue_event`](map-event-creation.md); `append_blank_event` can create one). The event has 1..8 action-button pages, each with an optional condition and a list of commands that can nest choices, conditions and battles (v1.19). It is meant for quest-stage NPCs that react to switches and variables set by earlier stages. See also the [quest state machine pattern](../patterns/quest-state-machine.md).

Python backend, mandatory re-indexing, one event append per map per transaction; the Ruby backend and `--no-reindex` are refused. System is read only (never written except the usual single `version_id` advance).

## Snapshot

```powershell
python tools/vxace_map_events.py PROJECT_INDEX --project PROJECT --map MAP_ID --template-event BLANK_ID --staged --output NEW_PRIVATE_SNAPSHOT
```

Same checks as the dialogue snapshot, plus `system_sha256`, `switch_count`, `variable_count`, `switch_names` and `variable_names` (id 1 first). `--staged` takes no graphic options and cannot be combined with `--donor-event`.

## Spec

```json
{"changes": [{"kind": "map_event", "locator": {"map_id": 1}, "proposal": "Quest elder with three stages.",
  "mutation": {"action": "append_staged_event", "template_id": 1, "new_id": 3, "name": "Quest Elder", "x": 3, "y": 4,
    "expected_map_sha256": "...", "expected_template_sha256": "...", "expected_system_sha256": "...",
    "pages": [
      {"condition": {}, "commands": [{"text": ["Please find my lost pendant."]}, {"set_switch": 1, "value": true}]},
      {"condition": {"switch1": 1}, "commands": [{"text": ["Any luck with the pendant?"]}, {"set_variable": 1, "op": "add", "value": 1}]},
      {"condition": {"variable": {"id": 1, "at_least": 1}}, "commands": [{"text": ["Thank you!", "Take this reward."]}, {"set_self_switch": "A", "value": true}]}]}}]}
```

`new_id` is the next maximum event id, `x`/`y` an unoccupied in-bounds cell and `name` unique (1..100 characters), exactly as for the dialogue event. All three hashes come from the snapshot; a stale map, template or System refuses.

### Page priority

The engine runs, on action-button interaction, the **highest-numbered page whose conditions are all met**. So order pages from the earliest quest stage (page 1, usually unconditional) to the latest; each later page needs a condition that only becomes true once its stage is reached. A page with no conditions that is not the last page only runs while no later page condition holds, which is usually what you want for page 1 but is reported as an impact warning so you can check it. Two pages with **identical conditions** are refused (the later page would hide the earlier one).

### Page fields

- `condition` (required, may be `{}`): any subset of `switch1` (switch id), `switch2` (switch id), `variable` (`{"id": N, "at_least": int}`, value is greater than or equal to `at_least`, bounds -99999999..99999999) and `self_switch` (`"A"`..`"D"`). Item and actor conditions are not supported.
- `trigger` (optional): only `"action"`. Autorun and parallel process are deliberately excluded (no termination proof).
- `commands` (required): 1..40 operations, in order (each nested body also holds at most 40):

| Operation | Native commands |
| --- | --- |
| `{"text": [1..4 lines]}` | `101` (no face, normal window, bottom) plus one `401` per line; the same literal text rules as the dialogue event (no control/escape codes, 500 characters per line) |
| `{"set_switch": id, "value": true/false}` | `121 [id, id, 0]` for ON, `[id, id, 1]` for OFF |
| `{"set_variable": id, "op": "set"/"add"/"sub", "value": int}` | `122 [id, id, 0/1/2, 0, value]` (constant operand, -99999999..99999999) |
| `{"set_self_switch": "A".."D", "value": true/false}` | `123 [ch, 0]` ON or `[ch, 1]` OFF |
| `{"choices": [2..4 texts], "cancel": index or null, "branches": [[cmds], ...]}` | `102 [choices, cancel_type]`, then per choice `402 [i, text]` with that branch's commands one indent deeper, then `404`. `cancel` null is cancel type 0 (disallow); an index `i` is cancel type `i+1` (that choice runs on cancel). There is no separate cancel branch (`403`). One branch list per choice, bodies may be empty. Choice text: 1..50 literal characters |
| `{"if": COND, "then": [cmds], "else": [cmds] optional}` | `111 [params]`, the `then` body one indent deeper, optional `411` + `else` body, then `412`. `then`/`else` need at least one command |
| `{"battle": troop_id, "can_escape": bool, "can_lose": bool, "win": [..], "escape": [..], "lose": [..]}` | `301 [0, troop_id, can_escape, can_lose]`. If either flag is true, or a `win` body is given, the editor layout follows: `601` (win body), `602` (escape body) only when `can_escape`, `603` (lose body) only when `can_lose`, then `604`. A body for a disabled outcome is refused. With both flags false and no `win` the battle is a bare `301` |
| `{"party": "add"/"remove", "actor": id, "initialize": bool}` | `129 [actor, 0 add / 1 remove, 0/1 initialize]`; `remove` cannot initialize |
| `{"common_event": id}` | `117 [id]` (a plain call) |
| `{"gold": +/-int}` | `125 [0 increase / 1 decrease, 0, abs]`, nonzero, up to 99999999 |
| `{"item": id, "amount": +/-int}` | `126 [id, 0 gain / 1 lose, 0, abs]`, nonzero, up to 99 |
| `{"transfer": {"map_id", "x", "y", "direction": 0/2/4/6/8, "fade": 0/1/2}}` | `201 [0, map_id, x, y, direction, fade]` (direct designation; 0 keeps the facing; fade 0 black, 1 white, 2 none) |
| `{"wait": 1..999}` | `230 [frames]` |

`COND` is exactly one of (the first key picks the form):

| Condition | `111` parameters |
| --- | --- |
| `{"switch": id, "is": true/false}` | `[0, id, 0 ON / 1 OFF]` |
| `{"variable": id, "op": OP, "value": int}` | `[1, id, 0, value, code]` (constant operand); OP / code: `==` 0, `>=` 1, `<=` 2, `>` 3, `<` 4, `!=` 5 |
| `{"self_switch": "A".."D", "is": true/false}` | `[2, ch, 0 ON / 1 OFF]` |
| `{"gold_at_least": int}` | `[7, amount, 0]` (party gold >= amount) |
| `{"has_item": id}` | `[8, id]` |

Indents: page-level commands are indent 0, a block body is one deeper, and the closing `404`/`412`/`604` and the `402`/`411`/`601`..`603` markers sit at the block's own indent. Nesting is limited to **4** levels, **40** operations per list and **200** generated native commands per page; the page ends with the terminator `0`. After generation every page is checked with the same pairing checker as guarded structure edits (`vxace_event_structure.validate_list`: balanced blocks, matching indent, one terminator). Unknown keys, extra keys on an operation and unsupported operations are refused. Page graphics are the template's blank graphic.

### Referenced databases (v1.19)

Troops, Actors, CommonEvents, Items and transfer destination maps are only read, never written, and each is bound by its **own** hash in the mutation. Only the files the pages actually use appear (an unneeded hash field is refused as an unknown key; a needed one that is missing or stale refuses):

| Used by | Required mutation fields | Checked |
| --- | --- | --- |
| `battle` | `expected_troops_sha256` | troop id exists in `Data/Troops.rvdata2` |
| `party` | `expected_actors_sha256` | actor id exists in `Data/Actors.rvdata2` |
| `common_event` | `expected_common_events_sha256` | id exists in `Data/CommonEvents.rvdata2` |
| `item`, `has_item` | `expected_items_sha256` | id exists in `Data/Items.rvdata2` |
| `transfer` | `expected_mapinfos_sha256`, `expected_destination_maps_sha256` (`{"<map_id>": sha}`) | map is in MapInfos, its `MapNNN.rvdata2` exists and `x`/`y` are inside its size |

Each hash is the SHA-256 of the Marshal dump of the file's root (array or hash). The `--staged` snapshot reports them as `troops_sha256`, `actors_sha256`, `common_events_sha256`, `items_sha256`, `mapinfos_sha256` (null when the file is absent) plus counts, and `--transfer-map N` (repeatable) adds `destination_maps` with each map's `sha256`, `width` and `height`. The impact report additionally checks the ids against the fresh index and warns for battles, transfers and gold removal.

### System ids

Every switch and variable id used in a condition or command must be `1..len-1` of the native `System.switches` / `System.variables` (the project's own count), read from `Data/System.rvdata2` and bound by `expected_system_sha256` (Marshal dump SHA-256). Raise the counts in the editor first if you need more ids.

## Examples (v1.19)

Choice-based recruit NPC (page 2 only after the self switch is on):

```json
"pages": [
  {"condition": {}, "commands": [
    {"text": ["Care to join me?"]},
    {"choices": ["Yes", "No"], "cancel": 1, "branches": [
      [{"party": "add", "actor": 1, "initialize": true}, {"set_self_switch": "A", "value": true}, {"text": ["Lead on!"]}],
      [{"text": ["Maybe later."]}]]}]},
  {"condition": {"self_switch": "A"}, "commands": [{"text": ["I am already with you."]}]}]
```
Needs `expected_actors_sha256`. Generated: `102 [["Yes","No"],2]`, `402 [0,"Yes"]`, `129 [1,0,1]`, ..., `402 [1,"No"]`, `101`/`401` at indent 1, `404`.

Boss battle with a lose branch, gated by a key item:

```json
{"condition": {"switch1": 1}, "commands": [
  {"if": {"has_item": 3}, "then": [
     {"battle": 7, "can_escape": false, "can_lose": true,
      "win": [{"set_switch": 2, "value": true}, {"item": 3, "amount": -1}],
      "lose": [{"text": ["You black out."]}, {"transfer": {"map_id": 1, "x": 5, "y": 5, "direction": 2, "fade": 0}}]}],
   "else": [{"text": ["Bring me the seal first."]}]}]}
```
Needs troops, items, MapInfos and the destination map hashes. Generated: `111 [8,3]`, `301 [0,7,false,true]`, `601`, `121`, `126 [3,1,0,1]`, `603`, `101`, `401`, `201 [0,1,5,5,2,0]`, `604`, `411`, ..., `412`.

Door that opens after a condition:

```json
{"condition": {}, "commands": [
  {"if": {"variable": 1, "op": ">=", "value": 3}, "then": [{"transfer": {"map_id": 2, "x": 4, "y": 5, "direction": 8, "fade": 0}}],
   "else": [{"text": ["The door is locked."]}]}]}
```
Needs the MapInfos and destination-map hashes.

## Verification and audit

Candidate verification requires all other map bytes and events identical, the new event to equal the factory result exactly, and System unchanged except for one `version_id` advance (as in v0.26). The audit records `action`, `page_count`, `pages`, `expected_system_sha256` and the `reference_hashes` of every referenced database. The databases and destination maps stay byte-identical.

The impact report lists every page's condition and command count (`staged.pages`), the priority note, and `staged.warnings` for: an unconditional page that is not the last, and any condition or command that uses an **unnamed** switch or variable (empty name in System).

## Recipe step

```json
{"type": "append_staged_event", "map_id": 1, "template_event": {"from_step": 1}, "x": 8, "y": 8, "name": "Quest Elder", "pages": [ ... ]}
```

`template_event` is an integer or `{"from_step": k}` pointing at an `append_blank_event` step on the same map; `pages` is the list above. Inside `pages`, a `battle` troop id may be `{"from_step": k}` (an `append_entry` step on table `troops`) and an `item` / `has_item` id may be `{"from_step": k}` (an `append_key_item` step). The referenced database hashes come only from the step's snapshot (the runner passes `--transfer-map` for every transfer destination); a recipe cannot supply them. The step creates the next event id (cross-checked against the audit). See [recipes](recipes.md).

## Limits

- No loops, labels, jumps, move routes, shops, scripts, autorun, parallel process, item/actor page conditions, graphics or faces. No cancel branch (`403`) for choices, no variable operands, and no variable (indirect) transfer destinations.
- `battle` uses a fixed troop (no random encounter); a battle without `can_lose` and a `lose` branch ends in Game Over on defeat, as in the editor.
- The page text is plain literal text; variable and switch semantics are not simulated. Check runtime behavior in the game.
- Self-switch state of the new event id may pre-exist in old saves; an appended static id can collide with runtime-created events.
- One staged event per map per transaction; at most 8 pages, 40 operations per list, nesting depth 4 and 200 generated commands per page.

## Native evidence (v1.18)

A two-step recipe on an editor-created project (blank event from donor 1, then a three-page Quest Elder) passed all postgates. In a smoke run the elder started on page 1; talking turned switch 1 ON and page 2 became active; the second talk added 1 to variable 1 and page 3 became active; the third talk turned self switch A ON. This confirms the 121/123 ON=0 encoding and the engine's highest-valid-page selection. The original project was unchanged.

## Native evidence (v1.19)

A four-step recipe on the same editor-created project (blank event, then Recruit, Door and Boss staged events) passed all postgates; the original project was unchanged. In a real-engine smoke run with auto-confirm:

- **Recruit:** choosing "Yes" added actor 8 (initialized), added 50 gold, waited and turned self switch A ON.
- **Door:** with variable 2 at 0 the else branch showed the locked text and called common event 1 without transferring; with variable 2 at 3 the player was transferred to 5,4 facing up.
- **Boss:** without item 1 the else text ran and no battle started. With the item, Battle Processing started troop 1; after the party was defeated the lose branch ran, showing the text and transferring to 3,3. The win body was skipped, so switch 2 stayed OFF and the item was kept, and the party was revived.

An existing save made before the change loaded and reloaded the map with the three new events (System `version_id` advance). The tests did not diff the encodings against events saved by the editor; the engine executed them as intended.
