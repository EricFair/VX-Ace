# Static balance analysis

`tools/vxace_balance.py` reads a fresh Project Reader index and reports damage, stat growth, matchups, troop rewards and shop economy without running any project code. It never edits the project, index or scripts, and nothing it prints authorizes mutation.

```powershell
python tools/vxace_balance.py PROJECT_INDEX --project PROJECT --json NEW_REPORT.json --markdown NEW_REPORT.md [--levels 1,10,20,50] [--var 12=5] [--actor 1] [--enemy 3] [--max-rows 200]
```

Use a fresh complete index. The usual freshness, source-integrity and index-integrity checks apply, and stale or changed input refuses. Report files must be new paths outside the source project and the index; at least one of `--json` / `--markdown` is required. Exit code 0 is success, 2 is a refusal (nothing is written on refusal).

## What it reports

- **Damage formulas.** Every skill and item with a damage type is parsed by a small restricted parser, not by evaluating Ruby. Supported: numeric literals, `+ - * / %`, parentheses, unary minus, `a.`/`b.` with `atk def mat mdf agi luk mhp mmp hp mp level`, and `v[n]`. Anything else (method calls, conditionals, `rand`, assignments, `;`, states, globals, `**`) is `opaque` with a reason and is never guessed. `v[n]` is evaluated with the `--var N=VALUE` default (0) and flagged as unresolved.
- **Actors.** Class parameter Table values at sampled levels (1, every 10th, and the max) plus the EXP curve from `exp_params`.
- **Matchups.** Each actor at the requested levels (the initial and max levels are always added) with the attack skill and the skills the class has learned by that level, against every enemy, giving base damage and hits-to-kill; enemy action skills against each actor likewise. Counts cover every row; output is capped by `--max-rows`.
- **Hit and evasion (v1.32).** Enemy-vs-actor rows also carry `hit_rate` (the enemy's HIT ex-parameter, feature code 22 data_id 0, summed over its features), `evasion` (the actor's EVA, data_id 1, summed over its class and actor features), `hit_chance` and `expected_damage` (= base damage x hit chance). For a physical skill (hit type 1) the chance is `success_rate x HIT x (1 - EVA)` clamped to 0..1, as in `Game_Battler#item_hit` / `item_eva`; certain-hit and magical skills use the success rate alone (magic evasion is not modelled) and show `null` HIT/EVA. An enemy with a physical HP attack in its actions whose HIT is 0 gets the warning `enemy_never_hits` ("Enemy can never hit (HIT 0%)"), the symptom of a clone whose features list was replaced without its HIT row. The markdown table has `hit`, `eva`, `chance` and `expected` columns.
- **Troops.** Total EXP and gold from member enemies, and drop items with chance.
- **Economy.** Item, weapon and armor prices and sell value, plus shops from native `302` / `605` commands in maps, common events and troops with exact evidence paths and price overrides.
- **Warnings.** Heuristic and labelled so: zero or negative base damage, one-shots at the actor's initial level (both directions), enemies needing more than 20 hits even with the best evaluated skill, missing troop enemies, and shop goods that are free, below database price, or priced under their half-price sell value.

## Limits

- Static editor data only. Custom scripts can change damage, EXP, stats and shops; the report cannot see them.
- Values are **base damage only**: element rate, variance, critical hits, guard, TCR/PDR/MDR, states and recover/drain handling apply afterwards and are not modelled. The value is truncated like Ruby `to_i`; integer division floors toward negative infinity and mixed float arithmetic stays float.
- The EXP curve uses the default VX Ace formula and is marked in the report as "default formula — verify against the project's scripts if customized".
- hp and mp are assumed full; actor stats exclude equipment, states and other features (the hit chance above uses features only: no equipment or state HIT / EVA). Enemy `level` is unavailable, so formulas using it are skipped and counted.
- Only HP damage and HP drain skills are matched up; MP damage is listed in the formula table only. Enemy actions are used regardless of conditions and ratings.
- Shops assembled by scripts or variables are not seen. Walk and byte budgets from the shared index reader apply and refuse instead of returning a partial result; narrow with `--actor` / `--enemy` if needed.

## Troop battles (v1.34)

```powershell
python tools/vxace_balance.py INDEX --project PROJECT --markdown out.md --troop 33 --troop 38 --levels 1,10,20 [--actor 1 --actor 2]
```

`--troop ID` (repeatable) adds a `troop_battles` section: the troop against the **party** at each `--levels` value (every member at that level, capped at its maximum). The party is `--actor` ids when given, else the System starting party, else every actor. `--enemy` is repeatable too and only narrows the enemy tables. For each troop and level the report gives:

- the sum of the enemies' **expected damage per turn** to the party, per enemy and per member. Enemy actions are chosen like the engine (ratings above max - 3, weighted by rating - (max - 3)); action conditions are ignored. Physical skills use the v1.32 hit chance (enemy HIT, member EVA); single-target hits are shared evenly, all-target skills hit every member, random-target skills count their hits;
- **turns to kill each member** with plain attacks (the whole troop using Attack on that member) and with the action mix;
- a rough **party survives N turns** estimate (party HP over expected damage) and the turn the first member is expected to fall;
- the party's plain-attack damage per turn and a pooled **race simulation** (party kills enemies in listed order, survivors hurt the party): `party_wins` or `party_wiped`, the turn and the HP left.

**Equipment:** each actor's initial equips (`equips`: weapon, then armor slots) add flat parameters (and HIT/EVA features) to the class stats; the labels are listed per member and the report says it is included. Parameter-rate features, states and skills other than Attack are not applied.

Not done (an item for 2.0): `--recipe-plan PLAN.json` to evaluate the troops a recipe plan would create. Until then, plan/run the recipe and point `--troop` at the new id.
