# Database, traits, states, skills, and equipment patterns

Use the VX Ace database aggressively when it already expresses the mechanic. The database is visible to designers, stable, and naturally integrated with battle logic.

## Trait aggregation mental model

For actors, effective traits come from the actor, class, equipped items, and active states. Enemies contribute their enemy database traits plus active states.

This makes traits ideal for mechanics such as:

- elemental rates;
- state rates/resistance;
- parameter modifiers;
- extra/special parameter modifiers;
- attack elements/states;
- skill-type grants/seals;
- skill grants/seals;
- equipment permissions/locks/seals;
- action-plus and selected special flags.

Before scripting a resistance or equipment rule, check whether a native trait already models it.

## States

Use states when the effect:

- belongs to a battler;
- can be added/removed during play;
- should participate in normal battle state lifecycle;
- can be expressed through existing trait/effect fields or modest scripting extensions.

Do not use a switch as a substitute for a battler-local combat state.

## Skills/items

Keep data-oriented properties in the database:

- scope;
- occasion;
- hit type;
- success rate;
- damage type/formula/element/variance/critical;
- costs;
- standard effects;
- common-event effect when appropriate.

Move to RGSS3 when the mechanic requires custom targeting, persistent per-skill runtime state, cross-action coordination, unusual timing, or behavior that cannot be represented cleanly by the database effect model.

## Equipment

Use equipment traits for passive modifiers before inventing custom actor variables.

A custom stat is justified when it must:

- have its own aggregation semantics not expressible by existing traits;
- appear in UI as a first-class stat;
- be referenced by many mechanics;
- have persistent base/bonus state beyond existing parameters.

## Common-event effects

Skills/items can reserve a common event through their effects. This is useful for out-of-battle or post-use orchestration, but do not treat a common event as a replacement for battle calculations that belong in battler/action code.

## Review questions

Before adding RGSS3 ask:

1. Is there already a native trait/effect for this?
2. Could a state model the temporary part?
3. Could equipment/class/actor traits model the passive part?
4. Is the requested behavior really a targeting/timing change rather than a stat change?
5. Will designers need to configure this repeatedly in the database?
