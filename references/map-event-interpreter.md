# Map, Event, and Interpreter Lifecycle

This reference focuses on how VX Ace decides **which event page is active, which interpreter executes it, and why events can block or loop**.

## Data versus runtime

- `RPG::Map` / `RPG::Event` / event pages / event commands are serialized project data.
- `Game_Map` is the runtime representation of the current map.
- `Game_Event` wraps each map event and selects its active page.
- `Game_Interpreter` executes event-command lists.
- `Game_CommonEvent` manages active parallel common events.

## Map setup

When a map is set up, the runtime generally:

1. loads the corresponding `MapXXX.rvdata2` data;
2. updates tileset/map display state;
3. instantiates a `Game_Event` for every map event;
4. builds active parallel common-event runtime objects;
5. refreshes tile-event/passability-related state;
6. prepares scrolling/parallax/battleback information.

This matters when debugging a problem that appears only after transferring maps: map runtime objects are rebuilt around the new map data, while persistent `$game_*` state such as switches/variables remains.

## Event page selection

`Game_Event` evaluates pages from highest priority to lowest and selects the first page whose conditions pass.

Therefore:

> A later page can silently shadow an earlier page even when the earlier page's conditions are also true.

Default page-condition categories include:

- switch 1;
- switch 2;
- variable threshold;
- self switch;
- required item in party;
- required actor in party.

For variable conditions, the normal model is a threshold comparison rather than equality. Debugging should therefore inspect both the current variable value and which later pages may also match.

## Refresh behavior

Changing switches, variables, self switches, inventory, or party composition can cause event-page eligibility to change. The runtime uses map/event refresh behavior to select a new page.

When debugging “the event graphic/trigger changed unexpectedly,” inspect:

1. all pages in reverse priority order;
2. all conditions on those pages;
3. recent switch/variable/self-switch writes;
4. item/actor party membership conditions;
5. whether a script changes refresh behavior.

## Trigger ownership

### Action/touch-type and autorun map events

These ultimately run through the **main map interpreter**. The map interpreter processes one command stream and then looks for the next starting event.

Implication: a stuck autorun can monopolize map execution because it becomes eligible again immediately after the interpreter completes unless its condition is turned off or its active page changes.

### Parallel map events

A parallel-process page owns a dedicated `Game_Interpreter` instance tied to that event runtime object. It is updated independently while the page remains active.

Implications:

- multiple parallel events can run concurrently;
- per-frame loops can become expensive;
- changing away from the parallel page removes that page's interpreter;
- parallel behavior can race with other events by reading/writing the same switches/variables.

### Common events

- **Autorun common events** feed the map's main interpreter when their activation switch is on.
- **Parallel common events** are represented by `Game_CommonEvent` runtime objects and maintain their own interpreter while active.

Treat the activation switch as ownership-critical state. A parallel common event that is “mysteriously still running” usually needs its activation switch and refresh/update path inspected first.

## Interpreter execution model

`Game_Interpreter` owns:

- map/event identity context;
- current command list;
- command index;
- branch state;
- resumable execution state;
- nested common-event/interpreter depth.

Event commands are dispatched by command code to corresponding interpreter handlers.

The interpreter can yield across frames for waits/messages/movement/battle and resume later. This is why “script code inside an event” must be reasoned about as part of a resumable command stream rather than as a single atomic function.

## Nested event calls

Nested common-event execution increases interpreter depth. The default engine protects against runaway recursive event calls with a depth limit.

If a project hits an event-overflow error, look for:

- common event A calling B while B calls A;
- a common event directly calling itself;
- script-driven event invocation loops;
- a plugin that changes interpreter setup/call semantics.

## Map transfer debugging checklist

If an event works before a transfer but not afterward:

1. confirm the destination map ID and event ID;
2. check whether the relevant self switch belongs to the old map/event key;
3. check whether the switch/variable condition is persistent and still true;
4. inspect destination event-page priority;
5. verify any script references to “this event” or current map context;
6. check whether a common event assumes `same_map?` context;
7. inspect autorun/parallel activation switches;
8. verify transfer timing relative to interpreter completion.

## Performance rules

Avoid using a parallel event for work that can be triggered once by a state change.

Bad pattern:

```text
Parallel event every frame
→ scan entire party
→ scan all inventory
→ scan many map events
→ update one switch
```

Better patterns include:

- update the switch when the relevant state changes;
- use a common event called from the change point;
- cache derived state;
- run periodic checks only when truly necessary.

## Debugging trace format

For event bugs, produce a trace like:

```text
Map 12 / Event 7
Active page: 3
Trigger: Autorun
Conditions:
  Switch 41 = ON
Commands:
  -> Common Event 8
  -> Variable 17 += 1
  -> Transfer Player

Potential loop:
Page 3 never turns Switch 41 OFF and remains highest matching page.
```

Never invent the IDs or names; derive them from the project index or ask for the relevant event data.
