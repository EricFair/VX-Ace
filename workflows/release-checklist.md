# Release checklist — shipping a VX Ace game

Use this before handing a build to players. Every step runs against a fresh index or a disposable copy; the working project is never modified by the tools. Items marked *manual* need the editor or a person.

## 1. Freeze and snapshot

- Close the editor, back up the project folder, and note the version you are shipping.
- `python tools/vxace_project_validator.py PROJECT --output NEW_DIR` — every `Data/*.rvdata2` should round-trip; investigate any failure before release.
- `python tools/vxace_project_reader.py PROJECT --output NEW_INDEX` — the fresh index used by the steps below.

## 2. Content checks (read-only)

| Check | Command | Look for |
|---|---|---|
| Missing/miscased graphics and audio | `vxace_asset_audit.py NEW_INDEX --project PROJECT --output NEW_DIR --rtp RTP_DIR` | unresolved references; files that only exist in the RTP (see step 4) |
| Event logic | event lint ([search and diagnostics](../references/search-and-event-diagnostics.md)) | autoruns without termination, unreachable pages, common-event cycles |
| Script conflicts | `analysis/script-compatibility.md` in the index | duplicate method overrides, load-order dependencies |
| Notetags | `vxace_notetags.py` | unrecognized tags (typos) and case mismatches |
| Text | `vxace_text_export.py --markdown` | overlong lines, bad control codes, out-of-range `\V[n]`/`\N[n]` |
| Balance | `vxace_balance.py --levels 1,10,20,...` | zero-damage matchups, one-shots, extreme hits-to-kill, free/below-cost shop goods |

Every report is heuristic evidence; decide each finding, do not "fix" blindly.

## 3. Runtime checks

- `vxace_smoke.py stage PROJECT --work NEW_WORK` then `run --mode normal` (and `--start save:N` with a save from the previous public build) — boot, first map, crash capture, old-save loading.
- *manual:* play the opening, one full battle, shop, menu save, quit, full restart and Continue.
- *manual:* if the update changes saved data, load a save from the last public version (see [data and save lifecycle](../references/data-and-save-lifecycle.md)).

## 4. Debug and test-only code

- Remove or `$TEST`-guard debug scripts (for example the [playtest logger](../templates/rgss3/playtest_debug_logger.rb) is already inert outside Playtest).
- Never ship a smoke-test copy: its harness is inert without the launcher's nonce, but it is still extra code.
- *manual:* turn off debug switches/variables and test-only events, transfer points and items.

## 5. RTP, fonts and packaging (manual, editor)

- **RTP:** players without the VX Ace RTP installed cannot load RTP-only assets. Either tell players to install the RTP, or copy every used RTP file into the project (the asset audit lists which references resolve only through the RTP) and set `RTP=` empty in `Game.ini`.
- **Fonts:** custom fonts go in a `Fonts` folder next to `Game.exe`; check the license allows redistribution.
- **Game.ini:** confirm `Title`, `Library=System\RGSS301.dll` and `Scripts=Data\Scripts.rvdata2`.
- **Compress Game Data** (File menu) creates `Game.rgss3a` and a distributable folder; optionally include RTP data there. Test the *compressed* output: run its `Game.exe` from a different folder on a machine or account without the editor.
- Licenses: credit third-party scripts, music and graphics as their terms require.

## 6. After release

- Keep the shipped build, its saves and the fresh index from step 1; they are the baseline for the next update's old-save and [schema comparison](../references/schema-comparison.md) checks.
