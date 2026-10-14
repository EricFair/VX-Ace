# RGSS3 Compatibility Rules

## Runtime target

Standard RPG Maker VX Ace uses RGSS3 based on Ruby 1.9.2. Code intended for standard VX Ace must be written for that environment unless a modified runtime is explicitly confirmed.

## Rules

- Do not assume modern Ruby syntax or standard-library behavior.
- Avoid version-sensitive conveniences when a simple Ruby 1.9-compatible form is available.
- Do not assume gems can be installed.
- Do not assume filesystem/network access appropriate to modern desktop Ruby applications.
- Do not assume Unicode behavior matches modern Ruby.
- Do not assume threads, native extensions, or external processes are appropriate merely because Ruby supports related concepts elsewhere.

## Script placement

Normal custom scripts are generally placed in the Script Editor under the Materials area and before the engine's final main process section. Exact ordering matters when scripts depend on or patch one another.

For every custom script, specify:

- whether it must appear above/below another script;
- which classes/methods it changes;
- configuration section;
- required database setup;
- whether a new game is required;
- whether existing saves are expected to remain compatible.

## Aliasing and overrides

Aliasing is not automatically safe. Two scripts may both alias a method yet still be order-dependent or semantically incompatible.

Before calling a patch compatible, compare:

1. same class/module?
2. same method?
3. aliases or full replacement?
4. expected call order?
5. return-value assumptions?
6. side effects?
7. instance variables introduced/required?
8. initialization/load timing?

## Namespacing

Prefer a unique module namespace for custom configuration and helper code. Avoid generic top-level constants/classes that may collide with common script libraries.

## Performance

RGSS3 code runs inside the game loop. Be suspicious of work repeated every frame:

- scanning every database entry;
- rebuilding arrays/hashes unnecessarily;
- parsing note fields repeatedly;
- repeated file IO;
- repeated regular-expression work;
- expensive sprite/window recreation;
- large parallel-event workloads.

Cache immutable derived data when appropriate, but ensure caches are initialized and reset correctly.
