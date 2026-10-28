# Minigame pattern

**Goal:** small self-contained challenges (button timing, fishing-style waits, number guessing) built from events, variables and the timer, with safe exits.

## Native-first design

- Run the whole minigame inside one **common event** called from a map event. One entry, one exit.
- Use **Button Input Processing** (Wait for button into a variable) for press-based input, **Control Timer** for time limits, **Input Number** for guessing, and **Random** in Control Variables for chance.
- All minigame variables are *scratch* and are reset at start. Only the final result is written to a durable owner.

## State ownership

| State | Owner | Notes |
|---|---|---|
| Round scratch (target, attempts, score) | Variables `VAR[mg_a]`, `VAR[mg_b]`, ... | Reset at start; meaningless after exit |
| Best score / unlocked prize | Variable `VAR[mg_best]` / Switch `SW[mg_prize_claimed]` | Written once at the end |
| Timer | Engine timer | Single global timer: avoid using it elsewhere simultaneously |
| Entry fee | Gold | Deducted only when the round actually starts |

## Step-by-step event layout

**Number guessing**

1. Control Variables `VAR[mg_target]` = Random 1..100; `VAR[mg_tries]` = 0.
2. Loop: Input Number into `VAR[mg_guess]`; add 1 to `VAR[mg_tries]`.
3. Conditional Branch: equal -> win text, Break Loop; less/greater -> hint text.
4. Conditional Branch `VAR[mg_tries] >= max` -> lose text, Break Loop. The loop must have this bound, not only the win condition.

**Button timing**

1. Set `VAR[mg_hits]` = 0; Control Timer start with a limit in seconds.
2. Loop: Show a cue (Show Picture or SE), Wait a random count (use Wait with a variable set from Random), then Button Input Processing into `VAR[mg_key]`. Compare with the expected button code (a project-specific constant: record it, do not guess).
3. Conditional Branch on Timer <= 0 (Conditional Branch > Timer) -> Break Loop.
4. After the loop: Control Timer stop; erase pictures; award by `VAR[mg_hits]` thresholds.

Note that Button Input Processing blocks until a press; a "reaction window" is faked by checking the timer or a frame counter after the press. If a true miss-on-no-press is needed, use a parallel helper or accept RGSS3 (see below).

**Fishing-style**

1. Show cast text; Wait a random 60-240 frames (Control Variables Random into `VAR[mg_wait]`; Wait uses it via a loop of Wait 1 with a counter, since Wait takes a fixed number).
2. Bite cue (picture/SE); Button Input Processing before the timer expires.
3. Success: roll the catch table (Random into a variable, Conditional Branches to Change Items); failure: text.
4. Provide the walk-away path: a Show Choices "Keep fishing?" each round.

**Exit/abort safety**

- Always stop the timer before leaving: Control Timer stop on every exit path, including cancel.
- Erase every picture the minigame shows (Erase Picture) on every exit path.
- Do not Transfer Player from inside the loop without first running cleanup.
- Disable Change Save Access / menu access during the round only if you also restore it on every exit path; prefer not to disable them.
- Put the cleanup in one tail section and Jump to Label to it from every abort.

## Pitfalls

- A loop with no iteration bound (infinite loop that freezes the game).
- Charging the fee before verifying the player can afford it, or refunding inconsistently on cancel.
- The global timer left running into other scenes or a battle where it may trigger a timeout event.
- Reusing the scratch variables used by another system.
- Treating Input Number digits as unbounded: set sensible digit count.
- Random seeds: Random in Control Variables is fine for casual use; do not rely on reproducibility.

## Test checklist

- Win, lose, and cancel on every prompt.
- Timer expiry mid-input; timer state afterwards.
- Pictures gone after every exit path.
- Fee and prize amounts; best-score logic.
- Save/load between rounds (not mid-round; mid-round saves from the menu are blocked while an event runs).
- **Old save** from before the minigame: prize switch OFF, best score 0.
- Battle triggered right after the minigame: no leftover timer.

## When RGSS3 is justified

- True real-time input windows, moving cursors, or dexterity games. Prefer a dedicated `Scene_` with its own windows/sprites, entered through a script call from an event, and exited back to the map by `SceneManager.return`; keep durable results in an existing saved owner. Verify the exact `SceneManager` methods in the project's scripts first.
