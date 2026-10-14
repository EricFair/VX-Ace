# Switch and variable architecture

Switches and variables form the backbone of native VX Ace game logic. Treat them like an API, not disposable editor slots.

## Naming

Name every durable switch/variable that has cross-event meaning.

Good:

- `Boss - Hollow King Defeated`
- `Quest - Broken Crown Stage`
- `System - Day Phase`
- `NPC - Mira Recruited`

Bad:

- `Switch 37`
- `quest2`
- `temp`

Temporary scratch variables may be generic only when tightly scoped and documented.

## Ownership categories

### Local event state
Use self switches when no other event needs the state.

### Global boolean fact
Use a switch.

### Mutually exclusive progression/state
Use a variable with documented values.

### Counters/numeric resources
Use variables when editor-based manipulation is sufficient.

### Complex structured state
When data becomes arrays/hashes/objects with invariants, graduate to RGSS3 and assign ownership to a `Game_*` object or custom project subsystem.

## Avoid boolean explosion

Do not encode a linear five-stage quest using five switches unless the stages can independently coexist.

Bad:

```text
QuestAccepted
QuestFoundCave
QuestKilledBoss
QuestReturned
QuestFinished
```

This permits contradictory states.

Better:

```text
QuestStage = 0..4
```

## Reserved ranges

For large projects, reserve ranges by subsystem only if the team finds it helpful. Names remain more important than ranges.

Example:

- 001-099 core/system
- 100-299 main story
- 300-599 quests
- 600-799 NPC/world flags
- 800+ temporary/testing

Do not renumber mature projects just to satisfy this convention.

## Write ownership

For every important state value, know which events/scripts are allowed to write it. Many bugs come from a second event unexpectedly resetting or incrementing shared state.

## Debugging rule

When a symptom appears state-related, log or inspect both:

- current value;
- last expected writer.

A future project reader should index every read/write reference to switches and variables.
