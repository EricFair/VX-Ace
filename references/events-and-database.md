# Events and Database — Decision Guide

## Prefer database configuration when

- the behavior is already represented by normal VX Ace features;
- the mechanic can be expressed through actor/class/equipment/state/enemy/skill configuration;
- a damage formula or standard feature produces the intended result without hidden side effects.

## Prefer map/common/troop events when

- the mechanic is primarily game flow or story logic;
- switches/variables are natural state representations;
- timing is discrete and tied to player actions, map events, or battle conditions;
- designers should be able to maintain it in the editor without touching code.

## Prefer RGSS3 when

- the mechanic changes engine behavior across many objects/maps;
- the same complex logic would otherwise be duplicated extensively;
- a new UI/scene/window is required;
- new persistent runtime state is required;
- battle/map/menu behavior needs a reusable extension point;
- eventing would require wasteful continuous polling or become unmaintainable.

## Use a hybrid when

The engine behavior is reusable but content should remain editor-driven. Common examples include:

- RGSS3 provides a system and script-call API;
- database notes/configuration opt content into the system;
- events trigger or react to the system;
- UI is implemented in RGSS3 while quest/story progression remains evented.

## Event anti-patterns

Flag these for review:

- many always-running parallel events that could be event-driven;
- magic-number switches/variables with no documented ownership;
- duplicated logic copied across many maps;
- autorun events that never clear their controlling condition;
- event pages whose conditions overlap accidentally;
- quest logic distributed across unrelated maps without an index;
- using common events as global mutable code without documenting callers;
- long chains of conditional branches where a reusable script/helper would be clearer.

## Database anti-patterns

- duplicating near-identical skills/items because a simple reusable mechanic is missing;
- placing substantial project logic inside opaque damage formulas;
- relying on undocumented note-tag syntax from a script without checking that script's parser;
- assuming a state/feature affects a custom battle system exactly as it affects default battle behavior.
