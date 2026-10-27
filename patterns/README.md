# Practical pattern library

These documents capture reusable VX Ace-native designs and anti-patterns. They are not project-specific templates: adapt names/IDs/state ownership to the actual project. Placeholders such as `SW[quest_started]`, `VAR[time_phase]`, `CE[craft_menu]` and `ITEM[ingredient_a]` stand for IDs you must look up in the real project; never invent them.

Use them before proposing RGSS3 for a common event/database problem. Where a pattern ends with "When RGSS3 is justified", the matching starter code lives in `../templates/rgss3/`.

## Index

### Event and state design

| Pattern | Use it for |
|---|---|
| [switch-variable-architecture.md](switch-variable-architecture.md) | Naming and owning switches, variables, self switches |
| [quest-state-machine.md](quest-state-machine.md) | Linear and branching quest stages |
| [one-time-and-gated-events.md](one-time-and-gated-events.md) | One-time rewards, locked doors, boss-gated changes |
| [cutscene-patterns.md](cutscene-patterns.md) | Cutscene structure and cleanup |
| [event-antipatterns.md](event-antipatterns.md) | Things to avoid in event design |
| [event-performance.md](event-performance.md) | Parallel processes, waits, frame cost |

### Database and battle

| Pattern | Use it for |
|---|---|
| [database-traits-states-skills.md](database-traits-states-skills.md) | Traits, states and skills before scripting |
| [damage-formula-boundaries.md](damage-formula-boundaries.md) | What belongs in a damage formula |
| [boss-battle-scripting.md](boss-battle-scripting.md) | Troop event pages, phases, spans, escape/lose handling |
| [bestiary-and-collections.md](bestiary-and-collections.md) | Tracking defeated enemies and found items |

### Gameplay systems

| Pattern | Use it for |
|---|---|
| [crafting.md](crafting.md) | Recipes, ingredient checks, failure paths |
| [shops-and-economy.md](shops-and-economy.md) | Shop Processing, price tiers, gold sinks, balancing |
| [party-management.md](party-management.md) | Recruit/leave, reserve, forced members, equipment |
| [day-night-time.md](day-night-time.md) | Time variable, tint, map-transfer refresh |
| [puzzles.md](puzzles.md) | Switch puzzles, push blocks, reset, softlock prevention |
| [minigames.md](minigames.md) | Timing, fishing-style, guessing, safe exits |

## Common rules

- Native first: Database -> events -> formula -> small RGSS3 -> deeper rewrite.
- Every persistent feature names its state owner and tests new game, save, load and an old save.
- Scripts are Ruby 1.9.2-compatible RGSS3; verify exact default/project method names before patching. Host `ruby -c` is diagnostic only; test in actual VX Ace.
