# Event anti-patterns

These patterns frequently create brittle VX Ace projects.

## Permanent parallel process for one-time work

**Symptom:** a parallel event checks a condition every frame just to perform logic that could have run when the state changed.

**Better:** trigger the work from the event that changes the state, or activate the parallel process only for the shortest necessary window.

## Autorun without a stop condition

**Symptom:** player appears frozen and no other map event proceeds.

**Cause:** autorun remains the active page/condition after reaching its end.

**Better:** invalidate the autorun condition before the event finishes.

## Switch-per-stage quests

Creates contradictory states and hard-to-trace resets. Use a stage variable for mutually exclusive linear progression.

## Copy-pasted common logic across maps

Leads to fixes applied in one map but not others. Extract stable shared logic into a common event or script subsystem.

## Giant common event

The opposite problem: a single common event with dozens of unrelated branches keyed by temporary variables becomes an undocumented dispatcher.

Prefer smaller common events with clear contracts.

## Magic IDs in scripts

Bad:

```ruby
$game_switches[137] = true
```

without any surrounding project-specific constant/documentation.

When IDs must be used in custom scripts, centralize them in named configuration/constants or resolve them from verified project knowledge.

## Heavy work every frame

Avoid repeatedly scanning large database arrays, rebuilding collections, parsing notetags, or allocating objects in frequently updated map/window/sprite methods.

Cache static data or react to state changes instead.

## Page-priority blindness

A correct-looking page never runs because a higher-numbered page also satisfies its conditions.

Always inspect all higher pages when debugging page activation.

## Transfer-dependent continuation without durable state

An event expects execution to continue after leaving its map.

Split the sequence and persist a stage/switch before transfer.

## Using RGSS3 for editor-simple content

A custom script that hardcodes ten shop inventories, dialogue branches, or chest rewards may be harder for designers to maintain than native events/database entries.

Choose scripting for reusable mechanics, not merely to avoid clicking in the editor.
