# Engine Architecture — Foundation Map

This file defines the architecture areas the skill must learn in detail. It is intentionally conservative until the default script corpus is ingested and verified.

## 1. Data layer

VX Ace projects use database and map data loaded into runtime objects. The agent must understand the distinction between:

- editor-authored database data;
- map/event data;
- runtime `Game_*` state;
- scenes/windows that present and manipulate runtime state;
- persistent save data versus temporary state.

Key categories in the engine map:

- actors and classes;
- skills and items;
- weapons and armors;
- enemies and troops;
- states;
- animations;
- tilesets;
- common events;
- system configuration;
- maps and map events.

## 2. Runtime game-state layer

The default script corpus contains `Game_*` classes representing live game state. The reference expansion should document ownership boundaries such as:

- global/system state;
- message state;
- switches/variables/self-switches;
- actors, party, and troop;
- battlers and battle actions;
- map, characters, player, followers, vehicles, events;
- interpreter/event execution.

The skill must learn where a new mechanic logically belongs rather than attaching state to an arbitrary global variable.

## 3. Presentation layer

VX Ace uses scene and window classes for user interface flow.

The skill must distinguish:

- scene lifecycle;
- window construction/disposal;
- selectable and command windows;
- map versus battle versus menu scenes;
- transitions between scenes;
- data refresh versus per-frame update.

## 4. Managers/modules

The engine includes manager-style modules for responsibilities such as scene flow, data/save handling, battle, sound/audio, and other shared functionality.

Verify exact methods and lifecycle ordering against the relevant default/project code before treating implementation details as stable extension points.

## 5. Extension points

The specialist should identify the narrowest useful extension point:

- data object method;
- runtime game-state method;
- event interpreter command or script call;
- scene/window behavior;
- manager hook;
- database formula or feature;
- event page/troop/common-event logic.

## 6. Architecture questions to answer before coding

For every nontrivial mechanic:

1. Where does the authoritative state live?
2. Who mutates it?
3. Who renders it?
4. What initializes it?
5. What resets it?
6. Does it need to be saved?
7. Does it need migration/default handling for old saves?
8. What existing scripts may touch the same methods?
9. Is an event/database implementation simpler and safer?
