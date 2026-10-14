# Data Loading and Save Lifecycle

This reference exists so the agent treats persistence as an engineering concern, not an afterthought.

## Database loading

`DataManager` loads the main VX Ace database files into `$data_*` globals. Core database categories include actors, classes, skills, items, weapons, armors, enemies, troops, states, animations, tilesets, common events, system data, and map metadata.

Individual map data is loaded separately when the current map is set up.

Architectural distinction:

- `$data_*` = editor-authored definitions;
- `$game_*` = mutable runtime state that can be saved.

## New-game setup

A new game recreates the runtime object graph, establishes starting party members, sets up the starting map/player position, and begins from fresh `$game_*` state.

Any feature with persistent state must define its new-game default explicitly or inherit a safe default from its owning object.

## Default save shape

VX Ace saves a small header for save-file display and a larger contents object containing runtime state.

The standard runtime set includes system, timer, message, switches, variables, self switches, actors, party, troop, map, and player state.

The engine uses Ruby Marshal serialization for these objects.

## Safe persistence strategies

### Strategy A — add an instance variable to an already-saved `Game_*` owner

Good for state that clearly belongs to an existing runtime object, e.g.:

- reputation on `$game_party` or `$game_system`;
- actor-specific progression on `Game_Actor`;
- game-wide feature flags on `Game_System`.

Old-save risk: an object loaded from an older save may not have the new instance variable initialized because `initialize` is not rerun during normal unmarshalling.

Mitigations:

- lazy getter default;
- `defined?(@field)` / nil-safe normalization when nil is not a valid state;
- explicit post-load migration hook.

### Strategy B — add a new key to save contents

Good when the feature owns a distinct object or subsystem that does not naturally belong inside an existing game object.

Old-save risk: older save contents will not contain the new key.

Mitigations:

- tolerate missing key;
- instantiate a default object on load;
- version and migrate the save schema when complexity grows.

## Do not persist presentation objects

Avoid serializing:

- windows;
- sprites;
- viewports;
- bitmaps;
- scene objects;
- fibers/threads unless the engine explicitly defines serialization behavior;
- objects that wrap non-marshallable native resources.

Persist model state and reconstruct presentation state after load.

## Interpreter persistence caveat

The default event interpreter has explicit serialization behavior because resumable execution state cannot be treated like an ordinary native execution object. This is a reminder that custom asynchronous constructs need deliberate save semantics.

Do not assume a custom Fiber, Proc, IO handle, graphics object, or external resource can be marshalled safely.

## Map version/update behavior

When loading a save created against older project data, the engine can refresh the current map when the project's data version changes. This is useful during development but is not a substitute for migrating custom script state.

A map refresh can also expose latent assumptions in scripts that cache event objects or map data across transfers/updates.

## Save-compatibility checklist

For every persistent feature, test:

1. **New game** — correct defaults.
2. **Save** — no Marshal error.
3. **Load same build** — state restored exactly.
4. **Old save** — missing new state handled safely.
5. **Map transfer after load** — no stale map/event references.
6. **Battle transition after load** — if feature touches battle state.
7. **Remove/disable feature** — understand whether old saves retain harmless extra data or become dependent on the script.

## Migration pattern

For larger systems, maintain a schema/version number in persistent state.

Conceptually:

```text
load save
  -> detect schema version
  -> apply migration 1 -> 2
  -> apply migration 2 -> 3
  -> normalize defaults
  -> continue game
```

Keep migrations deterministic and idempotent where practical.

## Feature ownership examples

| Feature | Likely persistent owner | Notes |
|---|---|---|
| Global reputation | `Game_System` or `Game_Party` | Pick based on semantic ownership |
| Actor talent points | `Game_Actor` | Per-actor state |
| Quest stage | variables or dedicated quest object | Native variables may be sufficient |
| UI cursor position | Usually not persistent | Reconstruct unless UX requires it |
| Procedural dungeon seed | dedicated persistent owner | Must survive load if dungeon must reproduce |
| Cached bitmap | Do not save | Rebuild from source/config |

## Anti-patterns

- adding a field and assuming old saves will call the new initializer;
- writing arbitrary globals that are not included in save contents;
- storing entire scene/window objects in game state;
- replacing `DataManager` save methods wholesale for one extra field;
- silently invalidating old saves without documenting it;
- serializing third-party runtime objects without testing Marshal behavior.
