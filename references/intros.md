# Run-once map intros

`add_intro` is a recipe macro for "do this once when the player first enters the map": an opening line, a switch that starts a quest, a cutscene made of waits and text. It is the **bounded substitute for autorun**. Autorun (trigger 3) stays refused everywhere because it has no termination proof; this macro uses a parallel process that is proved to stop (a self switch turned ON by its last command).

```json
{"type": "add_intro", "map_id": 1, "x": 7, "y": 7, "name": "Opening", "template_event": 1, "wait": 30,
 "commands": [{"text": ["The adventure begins."]}, {"set_switch": 1, "value": true}]}
```

Required: `map_id`, `x`, `y` (any free cell: the event has no graphic and priority below, so it neither shows nor blocks), `name`, `commands` (1..38 operations of the [staged command language](staged-events.md)), and exactly one of `template_event` (an existing blank event, or `{"from_step": k}`) and `donor_event` with `blank_x`/`blank_y` (the usual placement rule). Optional `wait` (1..999 frames, default 10).

## Expansion

An optional `append_blank_event`, then one `append_staged_event` named `name` with two pages:

1. Condition `{}`, trigger `parallel`, options `{"priority": "below"}`, commands `wait N`, then `commands`, then `{"set_self_switch": "A", "value": true}`.
2. Condition `{"self_switch": "A"}`, trigger action, options `{"priority": "below"}`, no commands (a bare terminator).

Records carry `macro` `add_intro` and `part` `a`/`b`; `from_step` afterwards refers to the event id; `plan` predicts it exactly. `from_step` is allowed inside `commands` for a battle troop, item/weapon/armor, actor (party, recover_all) and common-event ids, as in an `append_staged_event` page. Refusals: more than 38 commands (a wait and the self-switch command are added), a `transfer` anywhere in `commands` (see below), a bad `wait`, any key not listed above (no graphic, no trigger, no pages).

## Why it runs once and why it cannot repeat while a message is open

Checked against `Game_Event` and `Game_Interpreter` of the default scripts:

- `Game_Event#update` runs `@interpreter.setup(@list, @event.id) unless @interpreter.running?` and then `@interpreter.update`. `running?` is `@fiber != nil`, and the fiber stays alive for the whole list, so a page that is in the middle of its commands is never restarted, whatever it is waiting for.
- `command_101` (Show Text) and `command_102` (Show Choices) call `wait_for_message` (`Fiber.yield while $game_message.busy?`) before and after, and the interpreter's `run` starts with `wait_for_message` too. While a message of this event, or of any other event or common event, is open, the parallel interpreter simply sits in its fiber: nothing re-runs, nothing is skipped, and the message of another event is never overwritten by this one. If another event's message is open when the intro reaches its own text, the intro waits until it closes.
- The last command, `Change Self Switch A: ON`, sets `$game_map.need_refresh`. `Game_Map#update` begins with `refresh if @need_refresh`, **before** `update_events`, so on the next frame the event switches to page 2 (which has no trigger, hence no interpreter) before its page-1 interpreter could be set up again. The interpreter that was running is discarded together with the old page.
- The self switch is stored per map and event id (`$game_self_switches`), so the intro never runs again on that save, whatever the player does with the map afterwards. A new game, or a self switch reset by another script, runs it again.
- A parallel page does **not** lock the player (an autorun page would). The player can walk while the intro waits between messages; while a message is open the player cannot move (`Game_Player#movable?` is false while the message is busy). If the intro must hold the player in place, use a forced player `move_route` that waits, or keep the intro short.
- `wait N` first: the map fade-in after a transfer runs `$game_map.update(false)` (events still update) for roughly `fadein_speed` = 30 frames, preceded by a short `Graphics.wait`. A parallel page therefore starts running while the screen is still fading in; with the default `wait: 10` the first text can appear during the fade. Use `wait` of about 45 or more to let the fade finish. The wait is not required by the engine (the staged language only needs one wait in a parallel page), it is just a courtesy.
- Why `transfer` is refused: `command_201` reserves the transfer and yields; the old map is then replaced, its events (and this interpreter) are discarded, and the self-switch command after it never runs. The intro would run again on every entry. `battle` and `shop` are fine: their scenes return to the same map interpreter, which then continues. A `common_event` call runs as a child interpreter inside this fiber and is also fine, unless that common event itself contains a transfer (the macro cannot see inside it; check the called common event).
- A save made while the intro runs resumes it at the next command (`Game_Interpreter#marshal_dump` stores `@index + 1`).

## Using it

- Put the event on the map the player enters first (the start map) or on the map behind a door. It runs when that map is entered with the intro's self switch OFF; for an intro tied to a quest stage, set a switch in `commands` and gate the later events with that switch.
- For a one-time message on *stepping onto* a cell use `add_touch_trigger`; for "once per map entry, every time" there is nothing in the command language (the parallel page needs a switch or condition to stop).
- If the intro ends with a battle that can be lost, give it a `lose` branch; a battle lost without `can_lose` is a game over before the self switch is set, so the intro would run again on reload.

## Limits

No autorun, no graphic, no condition on the intro itself (nest `if` in `commands`), no repetition. Impact warns that page 1 is a parallel process and reminds that it stops through the self-switch page. In the real engine an intro waited its 45 frames, ran once and switched itself off; test your own intro text and timing in a smoke run or playtest of the copy.
