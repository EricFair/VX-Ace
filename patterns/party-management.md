# Party management pattern

**Goal:** actors join and leave, reserve members behave sensibly, forced members are handled, and equipment is never lost.

## Native-first design

- **Change Party Member** (Add/Remove) is the only recruit/leave command. Add has an "Initialize" option that resets the actor to their database starting state; use it deliberately (a rejoining actor normally should **not** be initialized).
- **Change Formation Access** and **Change Menu Access** control whether the player can reorder or open the menu. Disabling formation is the native way to force a lineup.
- The battle party holds a limited number of members (4 by default); extra members are *reserve*. Reserve EXP behaviour comes from a System tab option; verify its exact label in your editor.
- A removed actor is **not deleted**. Their level, EXP and equipment remain on the actor object and return when re-added.

## State ownership

| State | Owner | Notes |
|---|---|---|
| Who is in the party | `$game_party` (engine) | Mutate only through Change Party Member |
| Recruited at least once | Switch `SW[recruited_<name>]` | For dialogue/page conditions; do not infer from party membership |
| Currently available to rejoin | Switch `SW[<name>_available]` | Separate from "recruited" |
| Forced-member rule | Switch `SW[party_locked]` | Cutscene/chapter logic reads it |
| Joined chapter (optional) | Variable `VAR[<name>_join_stage]` | Only if rejoin logic differs |

## Step-by-step event layout

Recruit event:

1. Conditional Branch: `SW[recruited_x]` OFF.
2. Show Text; Change Party Member Add (Initialize ON the first time only).
3. Set `SW[recruited_x]` ON, `SW[x_available]` ON; Self Switch A to retire the recruit event.
4. Full party: adding to a full battle party places the actor in reserve; tell the player.

Leave event (story departure, temporary):

1. **Return equipment first:** Change Equipment for each slot with (None), so items go back to the inventory, then Change Party Member Remove. Alternatively leave gear on purpose and note it in the actor's rejoin text.
2. Set `SW[x_available]` OFF (or ON if they can be recalled at a camp).
3. Rejoin event: Change Party Member Add (Initialize OFF), `SW[x_available]` stays ON.

Forced members and locked lineups:

1. Set `SW[party_locked]` ON; Change Formation Access disabled; Add the required actor.
2. To force a reduced party for a scene, Remove others **after** returning their gear; record who was removed with a switch each, and restore them at scene end. A scene aborted midway (map transfer, battle loss) must still restore: run the restore from the next common entry point, not only from the scene's last page.
3. Permanent death/leave: Remove and set both switches OFF; never leave a ghost reference in page conditions.

Reserve and swap:

1. For a "swap partner" feature, the native formation menu is enough. Do not script it unless a rule (cannot remove the lead) needs enforcing: enforce with Change Formation Access plus forced Add order.

## Pitfalls

- Removing the actor holding unique equipment; the items stay on that actor and are unreachable.
- Initializing a returning actor, wiping their progress.
- Removing the last party member (the game over/empty-party state). Always Add before Remove when swapping.
- Using party membership as a story flag; it changes during scenes.
- Page conditions that test "actor in party" (a page condition can) while also depending on the player switching actors in the menu.
- Cutscene event graphics referring to a removed actor.

## Test checklist

- Recruit with party sizes 1, 3, 4 and full reserve.
- Leave with and without gear; check inventory afterwards.
- Rejoin: level/EXP/equipment preserved; Initialize behaves as designed.
- Forced scene interrupted by a battle loss and by a transfer; party restored.
- Menu/formation access restored after the scene.
- Save/load while the actor is away and while in reserve.
- **Old save** made before the recruit existed: switches default OFF, so the recruit event is still reachable; the actor exists in the Database.

## When RGSS3 is justified

- A rule that cannot be expressed with access flags, such as per-actor lineup constraints in the formation scene, or a roster of dozens of recruits with a custom list window. Add state to `$game_party`/`$game_system` with lazy defaults (see `templates/rgss3/save_safe_extension.rb`).
