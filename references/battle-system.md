# Battle System Architecture and Routing

This document is a **routing guide** for deciding where battle mechanics belong. It intentionally avoids copying the default battle source.

## Responsibility split

### `Game_BattlerBase`

Owns fundamental battler state and derived properties such as parameters, extra/special rates, features/traits, state presence, buffs/debuffs, skill/equipment eligibility, and related base calculations.

Patch here when a mechanic genuinely changes how a battler's properties are derived across the whole engine.

Risk: extremely high collision surface because many battle/core scripts alter parameter and trait behavior.

### `Game_Battler`

Owns active battler behavior layered on top of base properties: action handling, state changes, effect application, damage-result state, regeneration, and battle-time lifecycle behavior.

Use for effects that happen **to a battler** rather than for screen flow.

### `Game_Action`

Represents an actor/enemy action and is central to targeting/evaluation/application of skills/items.

Use when a rule is about:

- target selection;
- action validity/evaluation;
- applying a skill/item to targets;
- hit/evasion/critical/damage effect pipeline;
- custom action semantics.

### `Game_Actor`

Actor-specific concerns: class, experience, level, skills, equipment, actor traits, party-driven behavior.

### `Game_Enemy`

Enemy-specific concerns: enemy database data, action selection, drops, transformation, enemy-specific traits.

### `Game_Party` / `Game_Troop`

Unit-level battle membership and aggregate behavior. `Game_Troop` also participates in troop-event execution.

### `BattleManager`

Coordinates battle progression:

- setup;
- preemptive/surprise state;
- actor command progression;
- battle phases;
- escape;
- victory/defeat/abort;
- rewards and returning from battle.

Patch here only when the mechanic changes battle **flow**, not just numbers or visuals.

### `Scene_Battle`

Coordinates the battle screen, windows, input flow, action presentation, and communication with `BattleManager`.

Patch here for battle UI/control orchestration, not for a pure stat formula.

## Routing examples

| Mechanic | First place to investigate |
|---|---|
| Poison deals different periodic damage | battler/state effect pipeline |
| New resistance stat | battler base/traits + UI if displayed |
| Skill hits two random targets | `Game_Action` targeting |
| Enemy chooses actions differently | `Game_Enemy` |
| Victory grants custom resource | `BattleManager` reward/result flow or a narrower post-victory hook |
| Add “Limit” battle command | command window + `Scene_Battle`, with battler/action logic behind it |
| Change escape formula | `BattleManager` |
| Change equipment-derived ATK | `Game_Actor` / base parameter pipeline |
| Boss phase event at 50% HP | troop event may be enough; script only if requirements exceed eventing |

## Database-first opportunities

Before scripting, check whether the mechanic can be expressed with:

- states;
- features/traits;
- skill damage formulas;
- elements;
- state rates/resists;
- skill types;
- equipment types/features;
- troop battle events;
- common events invoked by skills/items.

A battle script should be justified by a limitation of the native data/event system.

## Collision checklist

Before changing a core battle method, search the project for:

- the class name;
- the exact method name;
- aliases of the method;
- replacement definitions (`def method_name`);
- prepend-like/custom wrapper frameworks if present;
- `$imported` flags and dependency checks;
- script comments specifying required order.

Then classify each overlap:

- additive new method only;
- alias/wrapper;
- full override;
- monkey patch to constants/data;
- indirect dependency.

## Battle regression matrix

For core battle changes, test at minimum:

- normal attack;
- physical skill;
- magical skill;
- healing/recovery;
- state application/removal;
- critical path if relevant;
- guarding/substitution/counter/reflection if touched;
- actor and enemy as subject;
- KO/revival;
- victory;
- defeat (both can-lose and game-over paths if used);
- escape;
- preemptive/surprise if flow touched;
- save/load before battle if persistent state is involved.

## Avoid giant overrides

If a feature needs only one extra check/value, prefer a narrow hook around the smallest stable method.

A giant copied-and-edited default method creates:

- high conflict risk;
- poor compatibility with other scripts;
- upgrade/maintenance problems;
- difficulty proving what changed.

If an override is truly necessary, document the original responsibility, every behavior retained, and the scripts that also replace it.
