# Event performance and update discipline

VX Ace is capable of substantial event-driven games, but per-frame work should be deliberate.

## Think in update frequency

Ask how often the logic truly needs to run:

- once on interaction;
- once on map entry;
- when a switch/variable changes;
- once per battle turn;
- every few frames;
- genuinely every frame.

Choose the least frequent correct trigger.

## Parallel processes

Parallel events are not automatically bad. They are appropriate for continuous independent behavior such as timers, ambient systems, or monitoring that cannot be expressed reactively.

But many parallel events running unconditional checks on every map frame increase complexity and cost.

## Common strategies

- gate parallel logic behind a switch;
- use Wait commands where sub-frame precision is unnecessary;
- cache expensive script-call results;
- avoid repeated full-database scans;
- avoid creating bitmaps/windows/sprites inside recurring event script calls;
- move system-wide continuous mechanics into one well-owned subsystem rather than many duplicated map events.

## Map-local versus global systems

Map-local ambient behavior belongs in map events when it dies naturally with the map.

Cross-map persistent systems often belong in a common event or RGSS3 subsystem, depending on complexity.

## Performance debugging

When a map stutters:

1. compare with parallel events disabled;
2. inspect custom move routes and pathfinding;
3. inspect recurring script calls;
4. inspect picture/sprite/window creation;
5. inspect custom `update` aliases/overrides;
6. reduce frequency with waits or event-driven triggers;
7. profile the smallest suspected subsystem rather than rewriting everything.
