# Puzzle pattern

**Goal:** switch/lever puzzles and push-block puzzles that are solvable, resettable and cannot softlock the player.

## Native-first design

- **Switch/lever puzzles:** each lever is an event with its own Self Switch for its position; a single *checker* decides success.
- **Push blocks:** an event with a pushable behavior built from Set Move Route, with the block's resting position tracked by the map itself (the event's location), not by variables, unless the puzzle must persist across map leaves.
- Prefer a **solution check at one place** over each lever knowing the answer.

## State ownership

| State | Owner | Notes |
|---|---|---|
| Lever position | Self Switch A of that lever | Local to the event |
| Puzzle solved | Switch `SW[puzzle_<name>_solved]` | Written once by the checker; read by door/chest pages |
| Combination progress (sequence puzzles) | Variable `VAR[puzzle_<name>_progress]` | 0..N, reset on error |
| Block position | The block event's X/Y while the map is loaded | Reset on re-entry unless persisted |
| Persisted block position (optional) | Two variables per block | Only when the puzzle must survive leaving the map |

## Step-by-step event layout

**Lever puzzle (any-order toggle):**

1. Lever event page 1: Self Switch A OFF; action: Play SE, set Self Switch A ON, Call Common Event `CE[puzzle_check_<name>]`.
2. Lever page 2 (Self Switch A ON): action: toggle back OFF and call the checker.
3. Checker: Conditional Branch on each lever's Self Switch is not possible for other events directly via the page-condition UI, so mirror each lever into a switch `SW[lever_<n>]` set by the lever (ON/OFF together with its self switch), then test those in the checker. If all required values match, set `SW[puzzle_solved]` ON and play feedback.

**Sequence puzzle:** each lever adds to `VAR[progress]`: if the lever is the expected next one, +1; otherwise set `VAR[progress]` to 0 and play an error SE. When it reaches N, set the solved switch.

**Push block:**

1. Block event, Action trigger, Same as Characters priority. On interaction, Set Move Route for the block to move one tile **away from the player**. The route should stop if blocked: leave "Skip if cannot move" ON so a wall stops it cleanly.
2. Also give the block a route-blocking check in a Conditional Branch (Script call or by terrain) if other events must stop it. Keep this check minimal.
3. Goal tiles: parallel or autorun is avoided; instead, a checker run after every push compares block positions using Control Variables from the block events' Game Data > Character > Map X/Y, into scratch variables.
4. When all blocks are on goals, set `SW[puzzle_solved]` ON and lock the blocks (turn a Self Switch to switch to a non-pushable page).

**Reset logic (mandatory):**

- Provide an in-room reset (a statue, lever, or re-entering the map). For levers: set each Self Switch OFF via Control Self Switch with the event ID (map event IDs, fixed in the map) and clear mirrored switches and progress variables.
- For blocks: Set Event Location back to starting coordinates (Set Event Location command, direct designation).
- If the puzzle is already solved, the reset must be disabled; otherwise it re-locks permanent content.

## Softlock prevention

- Never let a block be pushed into an unrecoverable position without a reset.
- Ensure the player always has a path out (an exit that does not depend on the puzzle).
- Doors that require the puzzle stay openable via `SW[puzzle_solved]` only; do not also require the player to stand in the room.
- Avoid puzzles that can be solved while the controlling event page is inactive (an off-screen page change from a map refresh).

## Pitfalls

- Pushing blocks over events with "Through" or into non-passable tiles; edge cases on a map border.
- Forgetting that a map refresh re-evaluates pages; a lever page tied to a self switch survives, a block's position survives only while the map instance is kept.
- Parallel checkers that run every frame; use after-action checks.
- Resetting self switches by event ID when events are later renumbered (maps keep IDs, but copy/paste creates new ones).

## Test checklist

- Solve in the intended order and in alternate valid orders.
- Wrong sequence, then reset, then solve.
- Push each block into every corner and against each wall; verify reset recovers it.
- Leave and re-enter the map mid-puzzle and after solving.
- Save mid-puzzle, load, continue.
- **Old save** from before the puzzle was added: solved switch is OFF, mirrored switches are OFF, blocks are at starting positions (events are replaced from map data when the map version changes).
- Battle encounters on the puzzle map do not alter state.

## When RGSS3 is justified

- Large grid puzzles (sliding tiles, rotating mirrors) where event counts explode, or when positions must persist and be queried generally. Store state in a saved owner with lazy defaults (see `templates/rgss3/save_safe_extension.rb`) and keep event commands as the trigger.
