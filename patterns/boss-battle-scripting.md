# Boss battle scripting pattern

**Goal:** multi-phase bosses, scripted dialogue, and safe win/escape/lose handling using troop event pages only.

## Native-first design

A troop's **Battle Events** page list is the native boss script. Each page has a **condition** and a **span**:

| Condition | Use |
|---|---|
| Turn No. (a + b*X) | Opening turn (a = 0), recurring actions every N turns |
| Turn End | Run after each turn |
| Enemy HP (n)% or below | Phase changes |
| Actor HP (n)% or below | Desperation lines, rescue moments |
| Switch | Externally triggered events |

| Span | Meaning |
|---|---|
| Battle | Runs once per battle |
| Turn | Runs once per turn when the condition holds |
| Moment | Runs every time the condition is checked while true |

Use **Battle** for phase transitions and intro lines. Use **Turn** for recurring boss behavior. Avoid **Moment** unless you understand how often it is evaluated.

## State ownership

| State | Owner | Notes |
|---|---|---|
| Phase | Enemy states and/or `VAR[boss_phase]` | Prefer a state on the boss if it must affect traits; a variable if only events read it |
| Boss defeated | Switch `SW[boss_<name>_defeated]` | Written once, in the Win branch of Battle Processing |
| Retry/lose handling | Map event after Battle Processing | Not inside the troop |
| One-time intro | Page with span Battle at turn 0 | |

## Step-by-step layout

1. **Intro:** Page 1: condition Turn 0, span Battle: Show Text lines.
2. **Phase 2:** Page 2: condition Enemy HP <= 50%, span Battle: Show Text; Change Enemy State (add a "Phase 2" state granting new traits via the Database) or Enemy Transform to a stronger form; set `VAR[boss_phase]` = 2. A Database state with trait changes is more maintainable than scripting stats.
3. **Recurring move:** Page 3: condition Turn 2 + 3X, span Turn: Force Action (boss uses a specific skill). Remember actions queued by Force Action are not a replacement for AI patterns; set normal skill rules in the enemy's Action Patterns too.
4. **Enrage / final line:** Page 4: Enemy HP <= 20%, span Battle.
5. **Adds:** Enemy Appear for hidden members placed in the troop.
6. **Battle Processing on the map event:** enable *Can Escape* only if escaping is intended; enable *Continue Even When Loser* if you want custom lose handling.
   - Win branch: set `SW[boss_defeated]` ON, grant rewards, advance the quest variable (see `quest-state-machine.md`).
   - Escape branch: reset any partial progress variable (`VAR[boss_phase]` to 0); decide whether the boss heals (new battle starts fresh anyway).
   - Lose branch (when Continue Even When Loser is on): restore the party, Transfer Player to a safe location, keep the boss undefeated.
7. For scripted-loss fights (story loss that continues), enable Continue Even When Loser and treat Lose as a normal story path; otherwise leave it off for Game Over.

## Pitfalls

- Phase pages with span Moment re-running every check.
- Using Enemy HP conditions that jump past a threshold in one hit: two phases may both be true; give pages a priority order and make later phases idempotent.
- Two pages setting the same switch or state.
- Phase variable persisting after an escaped/lost fight, so the next attempt starts in phase 2. Reset in Escape/Lose branches **and** in the turn-0 intro page.
- Win branch not run when the player escapes or loses; do not put defeat rewards inside the troop.
- Force Action on a dead or stunned boss; guard with conditions.
- Using the battle test (Database) context where map switches differ from the real game.

## Test checklist

- Win by normal damage; win by one-shot damage across thresholds.
- Escape (if allowed), then re-fight; phase and variables reset.
- Lose with and without Continue Even When Loser; party and position afterwards.
- Phase pages fire exactly once per battle.
- Boss with status immunity: ensure phase change does not rely on a state that can be resisted.
- Save before the fight, load, fight again.
- **Old save** before the boss existed: boss switch OFF, `VAR[boss_phase]` 0, troop pages come from the Database (the editor data, not the save).

## When RGSS3 is justified

- Conditions the page editor cannot express (e.g. combined HP of several enemies, per-skill counters), or boss UI elements. Prefer an alias on a narrow battle hook plus a notetag on the enemy; verify the exact `BattleManager`/`Scene_Battle` methods in the project's scripts first.
