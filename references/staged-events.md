# Guarded quest-stage event pages — v1.18

`append_staged_event` is a third action on the existing `map_event` change kind. It creates **one new event** on an existing map from an exact blank template event (the same predicate as [`append_dialogue_event`](map-event-creation.md); `append_blank_event` can create one). The event has 1..8 action-button pages, each with an optional condition and a short list of literal commands. It is meant for quest-stage NPCs that react to switches and variables set by earlier stages. See also the [quest state machine pattern](../patterns/quest-state-machine.md).

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
- `commands` (required): 1..40 operations, in order:

| Operation | Native commands |
| --- | --- |
| `{"text": [1..4 lines]}` | `101` (no face, normal window, bottom) plus one `401` per line; the same literal text rules as the dialogue event (no control/escape codes, 500 characters per line) |
| `{"set_switch": id, "value": true/false}` | `121 [id, id, 0]` for ON, `[id, id, 1]` for OFF |
| `{"set_variable": id, "op": "set"/"add"/"sub", "value": int}` | `122 [id, id, 0/1/2, 0, value]` (constant operand, -99999999..99999999) |
| `{"set_self_switch": "A".."D", "value": true/false}` | `123 [ch, 0]` ON or `[ch, 1]` OFF |

Every command has indent 0 and each page ends with the terminator `0`. Unknown keys, extra keys on an operation and unsupported operations are refused. Page graphics are the template's blank graphic.

### System ids

Every switch and variable id used in a condition or command must be `1..len-1` of the native `System.switches` / `System.variables` (the project's own count), read from `Data/System.rvdata2` and bound by `expected_system_sha256` (Marshal dump SHA-256). Raise the counts in the editor first if you need more ids.

## Verification and audit

Candidate verification requires all other map bytes and events identical, the new event to equal the factory result exactly, and System unchanged except for one `version_id` advance (as in v0.26). The audit records `action`, `page_count`, `pages` and `expected_system_sha256`.

The impact report lists every page's condition and command count (`staged.pages`), the priority note, and `staged.warnings` for: an unconditional page that is not the last, and any condition or command that uses an **unnamed** switch or variable (empty name in System).

## Recipe step

```json
{"type": "append_staged_event", "map_id": 1, "template_event": {"from_step": 1}, "x": 8, "y": 8, "name": "Quest Elder", "pages": [ ... ]}
```

`template_event` is an integer or `{"from_step": k}` pointing at an `append_blank_event` step on the same map; `pages` is the list above. The step creates the next event id (cross-checked against the audit). See [recipes](recipes.md).

## Limits

- No conditional branches, loops, choices, labels, item/actor conditions, autorun, parallel process, graphics or faces yet.
- The page text is plain literal text; variable and switch semantics are not simulated. Check runtime behavior in the game.
- Self-switch state of the new event id may pre-exist in old saves; an appended static id can collide with runtime-created events.
- One staged event per map per transaction; at most 8 pages and 40 operations per page.

## Native evidence (v1.18)

A two-step recipe on an editor-created project (blank event from donor 1, then a three-page Quest Elder) passed all postgates. In a smoke run the elder started on page 1; talking turned switch 1 ON and page 2 became active; the second talk added 1 to variable 1 and page 3 became active; the third talk turned self switch A ON. This confirms the 121/123 ON=0 encoding and the engine's highest-valid-page selection. The original project was unchanged.
