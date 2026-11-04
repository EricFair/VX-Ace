# Shopkeepers and inns — v1.33

Three pieces that close the gaps of the old shop workflow (an invisible counter event in front of a visible NPC, a full-heal item for an inn):

1. the **`shop`** and **`recover_all`** commands of the [staged command language](staged-events.md) (staged pages and [common events](common-event-append.md));
2. an optional **`graphic` and `options`** on the `append_dialogue_event` recipe step, so a dialogue event can be visible and `add_shop` still works on it;
3. the recipe macros **`add_shopkeeper`** and **`add_inn`**, which expand into ordinary guarded transactions (an optional blank event plus one `append_staged_event`). Both support `plan` and `--in-place`; `plan` predicts the event ids exactly.

Nothing here creates items, weapons, armors or actors; the goods and actors must already exist (or come from earlier recipe steps through `{"from_step": k}`).

## The `shop` command

```json
{"shop": {"goods": [{"type": "item", "id": 1, "price": null}, {"type": "weapon", "id": 3, "price": 600}], "purchase_only": false}}
```

`goods`: 1..32 entries, each exactly `type` (`item`/`weapon`/`armor`), `id` (1..999) and `price` (`null` = the database price, or 0..9999999 for a fixed price; 0 is free). No duplicate `(type, id)`. The rows are `302 [type, id, price_type, price, purchase_only]` then `605 [type, id, price_type, price]` per further good, built by the same function as `add_shop` and identical to the editor's layout (Shop Processing: type 0 item / 1 weapon / 2 armor; price type 0 database / 1 constant).

Bound hashes: `expected_items_sha256`, `expected_weapons_sha256` and `expected_armors_sha256` only for the goods types used; every id must exist. In a recipe a good's `id` may be `{"from_step": k}`.

**What the engine does** (`Game_Interpreter#command_302` of the default scripts):

```ruby
def command_302
  return if $game_party.in_battle
  goods = [@params]
  while next_event_code == 605
    @index += 1
    goods.push(@list[@index].parameters)
  end
  SceneManager.call(Scene_Shop)
  SceneManager.scene.prepare(goods, @params[4])
  Fiber.yield
end
```

- The shop scene ends the *command*, not the event: after the shop closes, the interpreter continues with the next command. Text written after a `shop` is shown after the player leaves the shop; commands that must happen before the shop (greeting, a switch) go before it.
- `purchase_only` is `@params[4]` of the `302` row; `Window_ShopCommand` hides the sell command when it is true. Prices come from `Window_ShopBuy` (`goods[2] == 0 ? item.price : goods[3]`).
- In battle (a common event called from a troop page or a skill) the shop is skipped.

## The `recover_all` command

`{"recover_all": "party"}` is `314 [0, 0]` and `{"recover_all": 3}` is `314 [0, 3]` (actor id 1..2147483647, bound by `expected_actors_sha256`). `Game_Interpreter#command_314` calls `iterate_actor_var(@params[0], @params[1])`: the first parameter is the designation (0 fixed, 1 variable; variable designation is not offered here) and the second the actor id, 0 meaning the whole party. The engine runs `Game_Battler#recover_all`: it clears every state (a fallen member is revived), then HP = MHP, MP = MMP. The party designation covers every member including reserve ones.

Project3 holds no editor-saved Recover All, so this layout rests on the engine script; verify one in the editor after first use.

## Dialogue event with a graphic

`append_dialogue_event` accepts an optional `graphic` (`{"character_name", "character_index", "direction", "pattern"}`, validated exactly like the [character graphic](character-event-graphics.md) of a staged page) and, only together with it, `options` (a non-empty subset of `walk_anime`, `step_anime`, `direction_fix`, `through` and `priority` = `below`/`same`/`above`).

- The sheet is bound by its asset hash exactly as before; the recipe runner takes it from the snapshot (`--character ...`) and, for a sheet in the RTP, from `--rtp`.
- **The default priority is `same`** when a graphic is set (as for a staged page since v1.30): the player bumps into the NPC and can talk to it from the side. Without a graphic the dialogue event keeps the template's priority, as before. An explicit `options.priority` wins. Impact and `plan` warn when a graphic dialogue event is below/above.
- `add_shop` works on such an event: the event is still exactly one page, stationary, unconditional, action-button, with one literal dialogue block; its graphic and priority are kept. (A *blank* event with a graphic is still refused.) So a visible shopkeeper is two recipe steps (`append_dialogue_event` with a `graphic`, then `add_shop` with `event_id: {"from_step": 1}`), or one step with `add_shopkeeper`.

```json
{"type": "append_dialogue_event", "map_id": 1, "template_event": 1, "x": 4, "y": 7, "name": "Guide", "lines": ["Welcome."],
 "graphic": {"character_name": "People2", "character_index": 0, "direction": 2, "pattern": 1}, "options": {"direction_fix": true}}
```

## `add_shopkeeper`

```json
{"type": "add_shopkeeper", "map_id": 1, "x": 5, "y": 7, "name": "Smith", "donor_event": 1, "blank_x": 2, "blank_y": 2,
 "graphic": {"character_name": "People2", "character_index": 0, "direction": 2, "pattern": 1},
 "lines": ["Steel for sale."], "goods": [{"type": "weapon", "id": {"from_step": 1}, "price": null}, {"type": "armor", "id": 2, "price": 300}],
 "purchase_only": false, "condition": {"switch1": 5}, "closed_lines": ["Come back after the quest."]}
```

Required: `map_id`, `x`, `y`, `name`, `graphic`, `lines` (1..4), `goods` (as above, ids may be `from_step`), `purchase_only`, and exactly one of `template_event` (an existing blank event or `{"from_step": k}`) and `donor_event` with `blank_x`/`blank_y` (the same placement rule as `add_treasure_chest`). Optional `condition` (a page condition: `switch1`, `switch2`, `variable` `{id, at_least}`, `self_switch`) and `closed_lines` (1..4, only with a non-empty `condition`).

Expansion (an optional `append_blank_event`, then one `append_staged_event`):

| Input | Pages |
| --- | --- |
| no `condition` | one page, condition `{}`: graphic, options `{"priority": "same"}`, commands `text lines`, `shop` |
| `condition`, no `closed_lines` | the same page with that condition (the event does not exist until it holds) |
| `condition` and `closed_lines` | page 1 condition `{}` with the same graphic and priority showing `closed_lines`; page 2 the conditional shop page (greeting, `shop`). The engine runs the highest page whose conditions hold, so the smith sells only after the condition |

Records carry `macro` `add_shopkeeper` and `part` `a` (blank event) / `b` (staged event); `from_step` afterwards refers to the staged event id; `plan` predicts it exactly. The page is an action-button page with priority same: the player stands next to the NPC and presses the action key. Fixed graphics only; there is no counter trick and no walking shopkeeper (a `move` field is not offered by the macro; use `append_staged_event` for a wandering merchant).

## `add_inn`

```json
{"type": "add_inn", "map_id": 1, "x": 6, "y": 7, "name": "Innkeeper", "template_event": 1,
 "graphic": {"character_name": "People1", "character_index": 3, "direction": 2, "pattern": 1}, "price": 50, "lines": ["Rest awhile."], "wait": 60}
```

Required: `map_id`, `x`, `y`, `name`, `graphic`, `price` (1..99999999), a template source as above. Optional `lines` (1..3 greeting lines, default `Welcome, traveler.`) and `wait` (1..999 frames between the recovery and the "rested" message).

One page, condition `{}`, graphic, priority same, with these commands:

1. `text`: the greeting lines, then `A night costs <price> <currency unit>. Stay?` as the last line of the same window (the currency unit is read from System, `G` when it is not plain text), followed by
2. `choices` Yes / No (cancel = No) —
   - **Yes**: `if gold_at_least price` then `gold -price`, `recover_all party`, the optional `wait`, and `You feel rested.`; else `Not enough gold.`
   - **No**: `Come again soon.`

The gold is only taken when the party has it, so the `gold` command never clamps. All texts are fixed English literals; for different wording use `append_staged_event` with the same commands. The recovery is the whole party (`314 [0, 0]`), reserve members included, and it revives fallen members.

## Plan and impact

`plan` and the impact report describe the shop and the recovery in plain words (`Shop: Potion (default price), Hunter's Dirk 600 G`, `Recover all: the entire party (HP, MP, states)`; impact: `staged.command_descriptions`, plan: summary lines `Page N: ...`) and carry the notes above as warnings. The plan reads the current currency unit and names from the simulated project state, so goods from earlier steps are named.

## Limits

- One shop per `shop` command; several `shop` commands in different branches are fine. No variable shops, no custom shop scenes or scripts, no selling price changes, no stock.
- Custom shop scripts, a replaced `Scene_Shop` or a changed `command_302`/`command_314` can change what the commands do; the tool cannot prove it.
- `add_inn` has no screen fade and no sound (the command language has neither); use a staged event if you need them. Texts are literal (no `\C[]` codes).
- The graphic sheet must exist in the project or the explicit `--rtp` root, exactly as for other graphic events.
