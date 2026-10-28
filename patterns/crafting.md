# Crafting pattern

**Goal:** the player combines ingredient items (and optionally gold) into a result item, with clear failure paths, using only editor features.

## Native-first design

Use one **recipe common event per recipe** plus one **menu common event** that offers the choice. No script is needed for a small recipe set (roughly under 15).

- Ingredients and results are ordinary Database items. Do not use the Key Item type for ingredients if the player should be able to see/discard them as normal stock.
- The recipe common event does check -> consume -> grant. All three live in the same common event so a single place owns the recipe.
- A crafting station is a map event that calls the menu common event; the menu common event never assumes which map it was called from.

## State ownership

| State | Owner | Notes |
|---|---|---|
| Ingredient counts | `$game_party` inventory (Change Items) | Never mirror in variables |
| Result item | `$game_party` inventory | |
| Recipe unlocked | Switch `SW[recipe_<name>_known]` | One per recipe, or one variable `VAR[recipes_known]` if recipes unlock in a fixed order |
| Scratch values (counts, chosen recipe) | Variables `VAR[craft_scratch_a]`, `VAR[craft_choice]` | Reset at the start of every call; never relied on across calls |
| Gold fee | `$game_party` gold | Optional |

## Step-by-step event layout

Menu common event `CE[craft_menu]`:

1. Show Choices listing known recipes only. Hide unknown ones by building the choice set in Conditional Branches on `SW[recipe_x_known]`, or use a recipe-count variable and several Show Choices.
2. Set `VAR[craft_choice]` from the choice, then Call Common Event `CE[craft_recipe_x]` per branch.
3. Cancel branch: Exit Event Processing.

Recipe common event `CE[craft_recipe_x]`:

1. Set `VAR[craft_ok]` = 1.
2. For each ingredient: Control Variables `VAR[craft_scratch_a]` = Game Data > Item `ITEM[ingredient_a]` (possessed count); Conditional Branch `VAR[craft_scratch_a] < N` -> set `VAR[craft_ok]` = 0.
3. Optional gold check: Conditional Branch Gold < cost -> `VAR[craft_ok]` = 0.
4. Conditional Branch `VAR[craft_ok]` == 1: **all tests happened before any consumption**. Inside: Change Items (ingredient, - N) for each, Change Gold (- cost), Change Items (result, + 1), Play SE, Show Text.
5. Else branch (failure): Show Text naming what is missing. Consume nothing.

For an optional **failure chance**, use Control Variables `VAR[craft_roll]` = Random 1..100, then Conditional Branch `VAR[craft_roll] <= success_pct`. Decide explicitly whether failure consumes ingredients and document it. Roll **after** the ingredient check and **before** consumption.

For **batch crafting**, use Input Number to set `VAR[craft_qty]`, clamp it with Conditional Branches against the scarcest ingredient, then Loop with a decrement and Break Loop at 0 so termination is provable.

## Pitfalls

- Consuming ingredient A, then finding ingredient B missing. Always test everything first.
- Granting past the inventory cap (default 99 per item): the surplus is lost. Test the held count of the result and refuse at the cap.
- Equipped ingredients are not part of inventory counts. Decide whether that is intended and say so in the text.
- Scratch variables shared with another common event that can interrupt (parallel process). Give crafting its own variables.
- Showing a recipe as available because a menu branch was copy-pasted without updating its switch.
- Key Item ingredients cannot be sold or discarded in the default menu; make sure that is intended.

## Test checklist

- Exactly enough ingredients: success, counts reach 0, result +1.
- One short on each ingredient in turn: failure text, **no** consumption.
- Insufficient gold with ingredients present.
- Result at 99 held.
- Cancel at every menu level.
- New game: recipes locked; unlock via the intended event; recipe appears.
- Save after unlocking, load: recipe still known, counts unchanged.
- **Old save:** a save made before the recipe existed loads; new switches default OFF and new variables 0; new items count 0, so no recipe is wrongly unlocked.
- Map transfer and battle between menu uses: scratch variables are not trusted.

## When RGSS3 is justified

- Dozens or hundreds of recipes where common-event duplication is unmaintainable.
- A dedicated crafting scene with an ingredient preview.
- Recipes data-driven from notetags (see `templates/rgss3/notetag_parser.rb`). Keep consumption in a method callable by a script call so events still own *when* crafting happens.
