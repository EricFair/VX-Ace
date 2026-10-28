# Adopting a reviewed staged copy (`vxace_adopt.py`)

`tools/vxace_adopt.py` is the only tool in this skill that writes to a real working project. Everything else edits disposable copies. Run it yourself, explicitly, after you have reviewed the result.

## When to use it

Only after all of these are done for the staged copy (or recipe result):

1. You read the plan, the impact analysis and the diff/semantic diff in the audit folder.
2. You tested the copy (smoke run or a manual playtest of the copy, never of your project).
3. You still want the change in the real project.

## Steps

1. **Close RPG Maker VX Ace and any running game.** `apply` and `undo` refuse while `RPGVXAce.exe` or `Game.exe` is running (checked with `tasklist`). There is no bypass flag.
2. **Plan** (read-only):
   ```
   python tools/vxace_adopt.py plan PROJECT --copy STAGED_COPY --audit AUDIT_DIR [--audit AUDIT_DIR2 ...] --output PLAN_DIR
   python tools/vxace_adopt.py plan PROJECT --recipe WORK/recipe-report.json --output PLAN_DIR
   ```
   For chained copies pass the audits in step order (the copy is the last one). With `--recipe` the report supplies every step audit and the final copy. Read `PLAN_DIR/adopt-plan.md`; it lists each file (replace/create), sizes and hashes, and prints the `plan_id`.
3. **Apply**:
   ```
   python tools/vxace_adopt.py apply PROJECT --plan PLAN_DIR/adopt-plan.json --backup-root BACKUP_ROOT --confirm PLAN_ID
   ```
   It re-verifies every hash, backs up each file it will replace into `BACKUP_ROOT/<UTC stamp>-<plan_id[:12]>/files/`, writes `adopt-record.json` there, then writes each file through a temp file plus `os.replace`, and verifies every hash afterwards. Any failure rolls the project back from the backup.
4. **Check or undo** any time:
   ```
   python tools/vxace_adopt.py status PROJECT --record BACKUP_ROOT/<stamp>/adopt-record.json
   python tools/vxace_adopt.py undo PROJECT --record BACKUP_ROOT/<stamp>/adopt-record.json --confirm RECORD_ID
   ```
   `status` reports `adopted`, `original`, `mixed` or `modified`. `undo` needs the `record_id` printed by `apply` (also inside the record) and restores the backed-up files; files the adoption created are removed.

Exit codes: 0 success, 3 deliberate refusal (JSON on stderr with `reason` and the offending items), 2 usage or input error.

## What is checked and refused

- PROJECT must be a real project (`Game.rvproj2` or `Game.ini`, plus `Data/`). COPY, plan output and BACKUP_ROOT must be outside PROJECT; links and junctions are refused.
- Audits must be successful copy-patcher audits (or a passing recipe report for this PROJECT with an unchanged original).
- **Freshness:** each file the audits changed must still have the recorded source hash in PROJECT (new files must not exist yet). Drifted files are listed and the plan is refused.
- **Exact change set:** the files that differ between PROJECT and COPY (whole tree) must equal the targets the audits declare, including `Data/System.rvdata2` when a version advance was recorded. An undeclared difference (for example you saved the project in the editor after staging) or a declared change missing from the copy is refused.
- Declared files in COPY must hash to the audit's final post-change hash.
- A copy containing the `VXA Smoke Harness` script slot is never adopted.
- Not compared and never touched: `Save*.rvdata2`, `vxa_smoke_*.txt`, `playtest_log.txt`, `Backups/`.
- `apply` also refuses a wrong `--confirm`, a plan whose content no longer matches its `plan_id`, and any file that changed in PROJECT or COPY since planning.
- `undo` refuses a wrong `--confirm`, a changed record, a missing or altered backup, and any file whose current hash differs from the adopted hash (it lists them, so your later edits are never overwritten).

## Limits

- There is no merge. If the project changed after the copy was staged, the plan is refused; re-index the project and re-run the change (or recipe) on a fresh copy.
- Only whole files are replaced or created; nothing is ever deleted from the project by `apply`.
- Backups are plain file copies kept by you under BACKUP_ROOT; keep them until you are happy with the result.
- Existing save files are not migrated; structural changes advance the project version so old saves reload maps, as the copy audit describes.

## Native evidence (v1.17)

On a stand-in copy of an editor-created project, the `example_cave.json` recipe staged four changes; `plan` listed exactly Enemies, Skills, Troops, Map001 and System. `apply` refused with the real editor process detected (`rpgvxace.exe`, open on a different project). With only that process check stubbed in a test harness, `apply` backed up and replaced the five files and `status` reported `adopted`; a smoke run of the adopted project found the new encounter and a random battle against the new troop in the real engine; `undo` then restored every `Data` file byte-identically.
