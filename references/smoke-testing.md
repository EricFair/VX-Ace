# In-engine smoke testing — v1.8

Use `tools/vxace_smoke.py` to run a project's own game inside the real RGSS3 runtime, in a **disposable copy**, with one test-harness script inserted before canonical Main. The harness drives a fresh boot (or a save), advances a bounded number of frames, catches uncaught errors, runs optional authored checks and writes a nonce-bound results file. The tool validates that file and reports.

## Trust model

- This runs the user's own game code (all their scripts, events and plugins) in a disposable copy. That is the same trust as pressing Playtest in the editor. It never runs the original project.
- The harness is inserted only through the existing guarded chain: validator, reader, `vxace_script_slots.py` snapshot, `script_slot`/`insert_before_main` spec, planner, impact review and the Python copy backend ([script-slot-insertion.md](script-slot-insertion.md)). All of its anchor, preservation, freshness and rollback rules apply. Customized Main anchors are refused.
- The harness is **inert unless the launcher sets a valid `VXA_SMOKE_NONCE`** and the matching `VXA_SMOKE_OUT` file name. A copy that is shipped by accident behaves like a normal game. Still, never ship or share the staged copy; it contains the harness and the user's content.
- Results are evidence from one timing-dependent run, not proof. They do not replace manual testing. `runtime_compatibility_proven` and `mutation_authorized` are always `false`.
- The harness writes only its results file into the copy. It never writes saves unless a suite does. Saves a suite creates stay in the disposable copy.

## CLI

```powershell
python tools/vxace_smoke.py stage PROJECT --work NEW_WORK_DIR [--suite SUITE.rb] [--ruby RUBY]
python tools/vxace_smoke.py run NEW_WORK_DIR --mode test|normal [--start new|save:N] [--frames 600] [--auto-confirm N] [--timeout 120] --json NEW.json --markdown NEW.md
```

`stage` needs a new work directory outside the project. It creates `validation/`, `index/`, `snapshot/`, `spec.json`, `plan/`, `impact.json`/`impact.md`, `audit/`, `copy/` and `smoke-stage.json` (project path, copy path, staged `Scripts.rvdata2` SHA-256, slot source SHA-256, suite SHA-256, script names, tool version). Step logs are in `logs/`. A failing step refuses with exit 2 and leaves the work directory for inspection; the copy patcher removes a failed copy itself. The slot is named `VXA Smoke Harness`; the slot source is the runtime `tools/smoke/vxa_smoke_runtime.rb` plus the optional suite (UTF-8, total at most 256 KiB, no NUL).

`run` verifies `smoke-stage.json` and that the copy's `Scripts.rvdata2` is unchanged, then launches `copy/Game.exe` (with `test` for `--mode test`) with the copy as working directory. A fresh random nonce and result file `vxa_smoke_<nonce>.txt` are used for every run, so you can run the same staged copy repeatedly. Outputs must be new paths outside the project and the copy. `--start save:N` loads save slot N (1..16, file `SaveNN.rvdata2` in the copy); `--frames` is the number of frames after which the run ends (1..1000000); `--auto-confirm N` presses the confirm key every N frames to advance messages and choices; `--timeout` is the wall-clock limit, after which the process tree is killed. A save to load must already exist in the copy; the tool does not create one. Launching `Game.exe` is Windows-only; other systems refuse.

## Results protocol

One tab-separated line each, appended and flushed per line: header `VXA_SMOKE`, nonce, Ruby version, `$TEST`, `$BTEST`; records `PASS|FAIL|ERROR|INFO`, name, detail; footer `END`, nonce, record count. Tabs and newlines in fields are replaced; details are capped. The tool refuses/flags a missing file, wrong header or nonce, missing or mismatched footer or count, unknown record types, a header `$TEST` that disagrees with `--mode`, records after the footer, duplicate headers and files over 4 MiB.

Built-in records: `boot`, `map_arrival` (map id, player x/y), `final_state` (scene, map, player position, whether the map interpreter is busy and its event id, party wipe), `runaway_event` (FAIL when the same main-map event keeps the interpreter busy for more than 600 frames, including autorun events that restart within 2 frames; frames spent waiting for message/choice input are excluded and reported once as INFO `waiting_for_message`), `gameover` (INFO) and `uncaught` (ERROR with the exception class, message and first backtrace lines).

Backtrace entries such as `{0059}:104:in ...` are mapped to script names by treating the number as the zero-based position in the staged `Scripts.rvdata2` order (the Script Editor order of the copy, including the inserted harness). This mapping was confirmed natively: a deliberate crash resolved to the harness, `Scene_Base` line 14 and `SceneManager` line 23, matching the default scripts. The report lists these as `script_refs`.

## Suite DSL

A suite is a plain Ruby 1.9.2 file appended to the harness slot. Blocks run later from hooks; do not touch `$game_*` at load time. Exceptions in any block are recorded and never end the run.

```ruby
VXA_Smoke.on_boot { VXA_Smoke.info('party', $game_party.members.size.to_s) }
VXA_Smoke.on_map  { VXA_Smoke.check('on a real map') { $game_map.map_id > 0 } }
VXA_Smoke.at_frame(60) { VXA_Smoke.press(:RIGHT, 30) }
VXA_Smoke.at_frame(200) { VXA_Smoke.check('still on map') { SceneManager.scene.is_a?(Scene_Map) } }
VXA_Smoke.on_finish { VXA_Smoke.info('gold', $game_party.gold.to_s) }
```

- `check(name) { bool }`: PASS for a truthy result, FAIL for falsy, ERROR when the block raises.
- `info(name, detail)`: INFO record.
- `on_boot { }`: after the new game or save is set up, before the map. `on_map { }`: first `Scene_Map` `post_start`. `at_frame(n) { }`: end of frame n. `on_finish { }`: just before the footer.
- `press(sym, frames = 1)`: virtual key (`:C`, `:B`, `:UP`, `:DOWN`, `:LEFT`, `:RIGHT`, ...). `Input.trigger?`, `press?`, `repeat?`, `dir4` and `dir8` see it; real input is unaffected.
- `VXA_Smoke.runaway_frames = N` changes the runaway threshold (default 600).

A full example is `tools/smoke/example_suite.rb`.

## Report and exit codes

The JSON report holds status (`pass`, `failed`, `incomplete`, `timeout`, `integrity_failure`), mode, start, frames, nonce, runtime info, all records, counts, duration, process exit code, problems, script references and the two evidence flags. Markdown is a readable copy.

- Exit 0: header and footer valid, at least one record, no FAIL or ERROR.
- Exit 3: any FAIL, ERROR (including uncaught), timeout or incomplete/invalid report.
- Exit 2: configuration, freshness or integrity refusal (also bad options, existing outputs, changed staged scripts).

## Limits

- No real input device: only the virtual keys above. Mouse and text input are not simulated.
- Timing dependent: results change with frame counts, auto-confirm rate and machine load. Long cutscenes or `Wait` sequences can trip the runaway check; messages waiting for input do not (use `--auto-confirm` to advance them).
- Windows only for the real launch; the process runs as the current user with no sandbox. Only stage projects the user already trusts to run.
- One script-slot transaction per staged copy. Scripts that replace `SceneManager`, the first scene, `Graphics.update` or `Input` may conflict with or disable the harness; a harness that fails to start shows as a missing or incomplete results file.
- Battle test (`$BTEST`) does not use the boot override.
- Passing proves only that these frames ran without the recorded failures. It does not prove compatibility, save safety or correct gameplay.

## Native evidence (v1.8)

Staged through the full validator/reader/slot/planner/impact/copy chain against an editor-created project with two unrelated custom scripts, then launched with the real `Game.exe`. Playtest and normal runs passed suite checks (party, start map, virtual DOWN input moving the player three tiles); `--start save:1` loaded an existing save; a deliberate uncaught error was captured with exit 3 instead of a blocking dialog and its backtrace mapped to script names; the header reported Ruby 1.9.2 and the correct `$TEST`. Launched without the tool, the same copy stayed on its title screen and wrote no result file. The original project was unchanged.
