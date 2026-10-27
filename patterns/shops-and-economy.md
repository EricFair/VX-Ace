# Shops and economy pattern

**Goal:** shops whose stock and prices follow progression, plus gold sinks that keep the economy meaningful, using Shop Processing and the Database.

## Native-first design

- **Shop Processing** takes a fixed goods list per command. Each row uses the Database price by default or a "Specify" override. Selling returns half the Database price (price-0 items and Key Items cannot be sold). Treat the half rate as fixed in standard VX Ace.
- **Progression stock and price tiers** are separate Shop Processing commands in Conditional Branches or on separate pages, not a script.
- **Purchase Only** (checkbox on the Shop Processing command) is the native no-buyback shop.

## State ownership

| State | Owner | Notes |
|---|---|---|
| Shop tier | Variable `VAR[shop_tier_<town>]` | 0 base, 1 upgraded, ... Written by the quest/boss event that upgrades it |
| Reputation/discount | Variable `VAR[reputation_<faction>]` | Only if used; one owner |
| Item base price | Database | Source of truth for buy and sell value |
| Special price | The Specify price on that shop row | Do not mirror in variables |
| Gold | `$game_party` | |

## Step-by-step event layout

1. Shopkeeper event: Show Text greeting; Conditional Branch on `VAR[shop_tier_town]`.
2. Per tier: one **Shop Processing** command listing that tier's goods. Higher tiers must list the lower goods again (a command cannot inherit); keep the tier table in design notes.
3. Optional price tiers: separate rows with Specify prices chosen by Conditional Branch on `VAR[reputation_x] >= N`. This is a few extra rows, not a formula.
4. After the command, a farewell Show Text. Nothing stateful happens inside the shop.
5. Gold sinks as events: inn (Change Gold, Recover All, fade), services (see `crafting.md`), donations/tickets, one-time permanent upgrades gated by a self switch (see `one-time-and-gated-events.md`).
6. **Limited stock:** stock is infinite in a normal shop. For limited stock, use a counter variable and a Show Choices "buy" menu with a Conditional Branch before Change Items/Change Gold, instead of a Shop Processing list.

## Balancing guidance

- Fix gold income per play hour at each stage first (enemy drops plus quest rewards), then price against it. Use a spreadsheet; keep the Database price column as the baseline.
- A basic healing consumable should cost a small fraction of one fight-set's income; tune per stage.
- Price equipment tiers at roughly 1.5-3x the previous tier, and let the player afford about one new piece after clearing a stage, not the whole set.
- Half-price selling is already a sink; avoid sellable loot that out-values shop stock.
- Provide at least one optional large late sink (convenience, cosmetic, minigame entry) so surplus gold stays meaningful.
- Compare a typical run and a completionist run: record gold held at each boss.

## Pitfalls

- Changing a Database price to adjust sell value also changes every Standard-priced shop row.
- Adding upgraded stock to one tier but not the others.
- Two events bumping the tier in different orders. Use "set to at least N" with a Conditional Branch.
- Purchase Only on a shop where the player is expected to sell quest loot.
- Crafting or loot loops that produce items worth more than their ingredients (infinite gold).
- Sinks on optional maps that players can skip, so gold piles up.

## Test checklist

- Each tier's stock at tier 0, 1, max, and an out-of-range value.
- Buy with exact gold, one short, and at the 99-item cap.
- Sell normal items, price-0 items and Key Items.
- Purchase Only shop shows no sell.
- Save/load around the tier upgrade.
- **Old save** from before the tier variable: it reads 0; confirm tier-0 stock is a safe fallback.

## When RGSS3 is justified

- Stock built from Database rules, per-shop sell rates, or persistent limited stock. Confirm exact `Scene_Shop`/`Window_Shop*` signatures in the project's own scripts first; they are not documented here from memory. Keep persistent stock state in an existing saved owner with lazy defaults (see `templates/rgss3/save_safe_extension.rb`).
