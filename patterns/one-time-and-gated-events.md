# One-time and gated event patterns

Use these patterns when a feature can stay inside VX Ace's native event/database layer. Prefer explicit ownership and stop conditions over clever but opaque event chains.

## One-time reward

**Goal:** an NPC/chest/event gives a reward once, then changes permanently.

Preferred structure:

1. Page 1 contains the interaction and reward.
2. At the end of the interaction, turn Self Switch A ON.
3. Page 2 requires Self Switch A and represents the completed state.

Use a project-wide switch instead of a self switch only when other maps/systems need to observe the completion state.

Do not use a global switch merely because it is familiar; self switches are a better local owner for local event state.

## Locked door with key

Preferred structure:

- Page 1: locked appearance/behavior.
- Conditional branch checks whether the party has the key item.
- If yes: optionally consume the key, play feedback, set Self Switch A.
- Page 2: open-door behavior and transfer/movement.

If the key opens multiple doors globally, use the item or a global progression switch as the shared requirement and reserve each door's self switch for whether that specific door has already been opened.

## Boss-gated world change

Use a global named switch because multiple maps may depend on the result.

Example ownership:

- Troop event or post-battle event owns `Boss Defeated = ON`.
- Individual map events use conditional pages based on `Boss Defeated`.
- Do not duplicate boss-state variables across maps.

## Conditional NPC

Use page conditions for stable state changes such as quest stage, recruited status, or boss completion. Use conditional branches inside a page for short-lived interaction choices.

Rule of thumb:

- **Page condition** = this NPC is fundamentally in a different state.
- **Conditional branch** = same state, different response during this interaction.

## Reusable interaction

When multiple events perform the same non-map-specific logic, move the shared logic to a common event and call it from each map event.

Do not move map-local movement routes, event-self-switch manipulation, or assumptions about `This Event` into a common event unless the context is explicitly designed for it.

## Shop with progression-dependent inventory

Prefer separate shop-processing branches/pages when the inventory differences are small and editor-visible. Graduate to RGSS3 only when inventory is dynamic enough that editor duplication becomes fragile.

## Failure modes to test

- repeated interaction;
- leaving and re-entering the map;
- saving before and after completion;
- using the key/reward elsewhere;
- page priority accidentally activating a higher page;
- changing the global prerequisite from another map.
