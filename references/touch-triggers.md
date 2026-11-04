# Touch triggers, movement and move routes

Staged event pages can start from a touch instead of the action button, can walk on their own, and the shared command language can move the player or erase the event. The pieces:

- Page `trigger`: `action` (default), `player_touch`, `event_touch`, `parallel` (needs a `wait`). Autorun stays refused. See [staged events](staged-events.md#triggers).
- Page `move`: `fixed`, `random`, `approach` or a bounded `custom` route. See [staged events](staged-events.md#move-routes).
- Commands `{"erase_event": true}` and `{"move_route": {...}}` (staged pages and [common events](common-event-append.md); `erase_event` and `this` routes are refused in a common event).
- A parallel, run-once variant ("run this once on map entry") is the `add_intro` macro, see [intros](intros.md).
- The `add_touch_trigger` [recipe](recipes.md) macro: a one-time (or repeatable) step-on trigger.
- The `add_monster` macro: a visible monster that starts a battle on touch. See [monsters](monsters.md).

## How a touch trigger starts

The start rules per trigger and priority (below/above: the player steps onto the cell; same: the player bumps into the event) are in [staged events, Triggers](staged-events.md#triggers). A below-priority touch page therefore needs the player to step on it; it cannot be bumped from the side. Impact says so for every touch page. A touch page with no commands never starts (`Game_Event#start` returns for an empty list).

## Examples

### Wandering villager

```json
{"type": "append_staged_event", "map_id": 1, "template_event": 1, "x": 5, "y": 5, "name": "Villager",
 "pages": [{"condition": {}, "move": {"type": "random", "speed": 3}, "commands": [{"text": ["Lovely day."]}]}]}
```

`move_type` 1, `move_speed` 3; the frequency and the default route object come from the template.

### Guard pacing left and right

```json
{"type": "append_staged_event", "map_id": 1, "template_event": 1, "x": 4, "y": 5, "name": "Guard",
 "pages": [{"condition": {},
   "move": {"type": "custom", "route": ["left", "left", {"wait": 30}, "right", "right", {"wait": 30}], "repeat": true, "skippable": true},
   "commands": [{"text": ["Halt."]}]}]}
```

`move_type` 3 with a repeating `RPG::MoveRoute`. `skippable` true lets the guard skip a blocked step instead of retrying it forever.

### Step-on cutscene

The player steps on the cell, is walked up two tiles, and then sees text. The route waits, so the text appears after the walk.

```json
{"type": "add_touch_trigger", "map_id": 1, "x": 7, "y": 6, "name": "Cutscene", "donor_event": 1, "blank_x": 2, "blank_y": 2,
 "commands": [{"move_route": {"target": "player", "route": ["up", "up"], "wait": true}}, {"text": ["Where am I?"]}]}
```

Generated page 1: `205 [-1, RPG::MoveRoute(repeat false, skippable false, wait true, up up terminator)]`, `505 [up]`, `505 [up]`, `101`/`401`, `123 ["A", 0]`. Page 2 is conditioned on self switch A.

### One-time trap that hurts through a common event

```json
{"title": "Spike trap", "steps": [
  {"type": "append_common_event", "name": "Spike Trap", "trigger": "none", "commands": [{"text": ["Spikes!"]}, {"gold": -20}]},
  {"type": "add_touch_trigger", "map_id": 1, "x": 6, "y": 6, "name": "Spike Trap", "donor_event": 1, "blank_x": 2, "blank_y": 2,
   "commands": [{"common_event": {"from_step": 1}}]}]}
```

The command language has no "Change HP" command, so HP damage has to live in a common event authored in the editor; reference it by its id (`{"common_event": 12}`) instead of the gold loss above. The trap fires once and then page 2 (self switch A) is empty. Use `"repeatable": true` for a trap that fires on every step.

## Notes

- `{"erase_event": true}` is `214`; the erase is temporary (`Game_Event#erase` sets `@erased`, and the event returns when the map is reloaded), so use a self-switch page for a permanent disappearance.
- Route entries are `down left right up random toward_player away_from_player forward backward`, `{"wait": n}` and `{"turn": direction}`; everything else is refused. `repeat: true` with `wait: true` is refused (deadlock).
- A `parallel` page repeats from the top every frame while its conditions hold; give it a condition that its own commands turn off (for example a self switch).
- The move-route layout has no editor-saved example; it follows `Game_Interpreter#command_205` (see [staged events](staged-events.md#move-routes)). The engine run is under Native evidence below.

## Native evidence

A six-step recipe ran on an editor-saved test project rebuilt as a 100x100 map with five events. It added:
- a blank event;
- a Villager (random move, speed 4, frequency 5, through);
- a Guard (custom repeat route left, left, right, right);
- a one-time Cutscene touch trigger whose Set Move Route moves the player up two tiles and waits;
- a one-time Trap touch trigger (-10 gold);
- a Vanisher that shows text and then erases itself.

The dry-run first refused a version of the recipe whose last event sat on an existing event's tile, the same refusal `run` gave. With the cell corrected, the plan's ids matched the run exactly (events 8–13).

In a real-engine smoke run:
- Stepping onto the Cutscene cell moved the player from 16,15 to 16,13 and set self switch A. Stepping on it again did nothing.
- The Trap took 10 gold once.
- Over 650 frames the Villager wandered from 10,20 to 9,24, and the Guard's x took exactly the values 10, 11 and 12.
- The Vanisher was erased.

An existing save loaded with all five events. The 205/505 layout follows `Game_Interpreter#command_205`, because the test project had no editor-saved Set Move Route to compare against. Check one in the editor after first use.
