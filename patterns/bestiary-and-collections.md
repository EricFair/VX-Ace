# Bestiary and collections pattern

**Goal:** track which enemies were defeated and which items/discoveries were found, with a displayable progress and rewards, preferring variables and switches.

## Native-first design

- **Small collections (up to roughly 30 entries):** one switch per entry, set by the event that grants or encounters it. A "collected count" variable is updated by that same event.
- **Bestiary via troop events:** each troop's battle event page (Span: Battle, condition: Turn 0) sets the "seen" switch; a page conditioned on enemy defeat (or Battle End logic in the post-battle map event) sets the "defeated" switch.
- Display with a **common event** that lists entries using Conditional Branches and Show Text, or Show Picture of a checklist.
- Rewards by milestone use a Conditional Branch on the count variable plus a one-time switch.

## State ownership

| State | Owner | Notes |
|---|---|---|
| Entry seen/defeated | Switch `SW[bestiary_<enemy>_seen]` / `_defeated` | Written only by that enemy's troop event |
| Kill counts per enemy | Variable `VAR[kills_<enemy>]` | Added by the troop event |
| Total completion | Variable `VAR[collection_count]` | Increment only on the OFF->ON transition |
| Milestone reward claimed | Switch `SW[collection_reward_<n>]` | One-time |
| Items found | Switch per item or inventory presence | Prefer the switch if the item can be consumed or sold |

## Step-by-step event layout

1. For each troop in the Database: add a battle event page: condition Turn 0 (Span: Battle) -> Conditional Branch `SW[x_seen]` OFF -> set it ON, add 1 to `VAR[collection_count]`.
2. Defeat: since a win ends the troop, record in the map-side or common event run right after the Battle Processing command (the Win branch), or via a troop page conditioned on the enemy's HP (see `boss-battle-scripting.md`) when the enemy is a single one. For multi-enemy troops, increment `VAR[kills_x]` in the Win branch of the Battle Processing command.
3. Display common event `CE[show_bestiary]`: Show Choices per category, then per entry a Conditional Branch showing the name if seen, otherwise "???".
4. Item collection: every pickup event ends with `CE[record_item_found]` using a number variable `VAR[collection_arg]` holding the entry index, or directly sets its switch and increments the count.
5. Milestones: Conditional Branch `VAR[collection_count] >= N` and `SW[collection_reward_n]` OFF -> grant, set the switch.

## Variables vs a small script

| Need | Variables/switches | Small script |
|---|---|---|
| Up to ~30 entries, manual listing | Good | Overkill |
| 100+ entries, auto-listing from Database | Event duplication heavy | Better |
| Per-enemy kill counts | Works (a variable each) | Cleaner (one Hash) |
| Auto-record every enemy without editing troops | Not possible natively | Hook in battle end |
| Persistence | Automatic with variables | You own old-save defaults |

## Pitfalls

- Incrementing the total each time instead of on first discovery.
- Marking "seen" on a troop that is used for a cutscene fight and was never actually visible.
- Same enemy in several troops; each troop needs the page, or use the Win-branch approach in one common event.
- Using inventory presence for consumable items (the entry disappears when used).
- Unbounded numbers of switches clutter the switch list; use naming prefixes and keep the project codex current.
- Variable maximums (the VX Ace variable range is large, but display windows have limited digits).

## Test checklist

- First sight, first defeat, repeat defeat: counts change only as designed.
- Fleeing from a battle: seen set, defeated not set.
- Multi-enemy troop, boss troop and an enemy shared across troops.
- Display list with none, some and all entries.
- Milestone claimed once; save/load before and after.
- **Old save** from before the bestiary: all switches OFF and counts 0. Decide whether past kills are unknowable (usually accept it and say so).

## When RGSS3 is justified

- Automatic recording across all enemies and items, a Hash-based kill table, and a dedicated list scene. Use a saved owner with a lazy default (see `templates/rgss3/save_safe_extension.rb`). Database-derived metadata (a description per enemy) can come from notetags via `templates/rgss3/notetag_parser.rb`.
