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
- **Troops.** Total EXP and gold from member enemies, and drop items with chance.
- **Economy.** Item, weapon and armor prices and sell value, plus shops from native `302` / `605` commands in maps, common events and troops with exact evidence paths and price overrides.
- **Warnings.** Heuristic and labelled so: zero or negative base damage, one-shots at the actor's initial level (both directions), enemies needing more than 20 hits even with the best evaluated skill, missing troop enemies, and shop goods that are free, below database price, or priced under their half-price sell value.

## Limits

- Static editor data only. Custom scripts can change damage, EXP, stats and shops; the report cannot see them.
- Values are **base damage only**: element rate, variance, critical hits, guard, TCR/PDR/MDR, states and recover/drain handling apply afterwards and are not modelled. The value is truncated like Ruby `to_i`; integer division floors toward negative infinity and mixed float arithmetic stays float.
- The EXP curve uses the default VX Ace formula and is marked in the report as "default formula — verify against the project's scripts if customized".
- hp and mp are assumed full; actor stats exclude equipment, states and other features. Enemy `level` is unavailable, so formulas using it are skipped and counted.
- Only HP damage and HP drain skills are matched up; MP damage is listed in the formula table only. Enemy actions are used regardless of conditions and ratings.
- Shops assembled by scripts or variables are not seen. Walk and byte budgets from the shared index reader apply and refuse instead of returning a partial result; narrow with `--actor` / `--enemy` if needed.
