# In-engine smoke testing — v1.8 (suite helpers, screenshots and `check`: v1.34)

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
python tools/vxace_smoke.py run NEW_WORK_DIR --mode test|normal [--start new|save:N] [--frames 600] [--auto-confirm N] [--timeout 120] [--screenshot LABEL@FRAME ...] --json NEW.json --markdown NEW.md
python tools/vxace_smoke.py check PROJECT --start-map ID ... --results NEW_DIR     # one-line feature check, see below
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

A full example is `tools/smoke/example_suite.rb`. Frame-number hooks are fine for simple probes; for anything that has to wait for the game use the sequential helpers below.

## Helpers for suites (v1.34)

Hand-written suites kept getting the same things wrong: an "idle" check that ignored parallel events, fixed frame waits instead of waiting for a condition, no screenshots and no way to play a battle. The runtime now ships helpers for exactly that. They are plain Ruby 1.9.2 module functions of `VXA_Smoke`.

**Scripts.** `VXA_Smoke.script { ... }` runs the block as one sequential script on a fiber: each wait pauses it, the game runs on, and the scheduler resumes it one slice per frame once the first map is up. Inside the block the helpers can be called bare (`goto 3, 5, 5`). When the script ends the run finishes (`script_done`, `final_state`), unless `VXA_Smoke.script(:finish => false) { }`. At the `--frames` limit an unfinished script is a FAIL `script_incomplete`, so `--frames` is only a watchdog. An exception inside the script is an ERROR `script` and ends it. `VXA_Smoke.sequence([[:goto, 3, 5, 5], [:wait_idle], [:talk, 'Marta']])` is the same thing as an ordered list of steps.

| Helper | Does |
| --- | --- |
| `idle?(ignore_parallel = false)` | true when the scene is `Scene_Map` and nothing is running: no message, no transfer, no reserved common event, no starting event, no map interpreter, no parallel event interpreter and no parallel common event interpreter (`ignore_parallel = true` skips the parallel ones, for maps whose parallel events never stop). `idle_reasons` lists what is busy. |
| `wait_until(timeout_frames, name = nil) { cond }` | script only: waits until the block is truthy; returns true, or records FAIL `wait_until_timeout` and returns false. |
| `wait_idle(timeout = 900, opts = {})` | script only: `wait_until` that `idle?` held for `:stable` (3) frames. While a message is up it presses confirm every `:confirm` (8) frames (0 = never); `:ignore_parallel => true`. |
| `wait_frames(n)` | script only. |
| `goto(map, x = nil, y = nil, dir = 0)` | reserves a player transfer (dir 0 keeps the facing; nil x/y = the System start spot, or the map centre) and, in a script, waits until idle. |
| `event(name_or_id)` / `events_named(name)` | the `Game_Event` on the current map (case-insensitive name); `event` raises when there is none. `expect_event(name)` records PASS/FAIL and an `event NAME` INFO (id, position, whether a page is active). |
| `talk(name)` | stands the player on a free tile next to the event, facing it (on the event itself for below/above-priority events) and presses the action key; in a script waits up to 30 frames for something to start (message, interpreter, starting event, battle), else FAIL. Follow it with `wait_idle`. |
| `step(dir, n = 1)` | script only: walks n tiles with virtual input, waiting for each move; stops early with INFO `step_interrupted` (an event, battle or message started: the monster bump) or INFO `step_blocked` (4 frames without moving). Returns true when all steps were taken. |
| `auto_battle(mode)` | `:attack` plays the battle menus (Fight, Attack, first target, every turn); `:win` kills the troop on its first battle frame; `:lose` zeroes the party; `:off`. Battle messages are confirmed. Each battle records INFO `battle_start` and INFO `battle`: troop id and name, result (`win`, `escape`, `lose`), turns (`$game_troop.turn_count`), frames, party HP before and after, mode. `VXA_Smoke.battles` returns the same as hashes (`:result`, `:turns`, `:hp_after`, ...) for checks. Without `auto_battle` a `wait_idle` during a battle times out (FAIL), which is the signal that the suite must choose a mode. |
| `screenshot(label)` | see below. |

## Screenshots

`VXA_Smoke.screenshot(label)` (anywhere, script or hook) or `vxace_smoke.py run ... --screenshot LABEL@FRAME` (repeatable, up to 20 per run) saves the screen **in the engine**: `Graphics.snap_to_bitmap`, each pixel read with `Bitmap#get_pixel`, then encoded as an **8-bit RGB PNG in pure Ruby** (zlib `Deflate` when the `Zlib` constant is available, otherwise stored/uncompressed deflate blocks with a Ruby CRC-32 and Adler-32; both give a valid PNG). A full 544x416 frame takes a few seconds in the Ruby interpreter and writes `vxa_smoke_<nonce>_shot_NN_<label>.png` into the copy (an INFO `screenshot` record names it). After the run the tool copies the PNGs, after checking the signature and size, into `<json stem>-screenshots/` next to the JSON report and lists them as `screenshots` in the report and under "Screenshots" in the markdown. No Python capture, DPI handling or `mss` is involved. Labels are letters, digits, `_` and `-` (other characters become `_`, 40 max).

## One-line check

```powershell
python tools/vxace_smoke.py check PROJECT --start-map ID [--x X --y Y] [--direction 2|4|6|8] [--expect-event NAME ...] [--step DIR:N ...] [--talk NAME] [--auto-battle attack|win|lose] [--screenshot LABEL[@FRAME] ...] [--frames 1800] [--mode test|normal] [--timeout 300] --results NEW_DIR
```

It stages one temporary copy (the normal `stage` chain) with a generated suite, runs it, **deletes the copy** and keeps only the results folder: `report.json`, `report.md`, `suite.rb` (the generated Ruby) and `screenshots/`. The generated script is: `goto` the map (and x/y), `auto_battle`, one `expect_event` per name, each `--step` followed by `wait_idle`, `talk` followed by `wait_idle`, then one `screenshot` per bare label, and an INFO `check_position`. With no steps, talk or battle it just waits for the map to go idle. `--screenshot LABEL@FRAME` is taken at that frame instead. Names must be 1..200 characters without control characters; `--results` must be a new folder outside the project; `--work-root` picks where the temporary copy lives; `--keep-work` leaves it for debugging. Exit codes are those of `run`; the printed JSON shows status, counts, screenshot files, `temporary_copy_removed` and the results folder.

## Examples

A talk, checked and photographed:

```powershell
python tools/vxace_smoke.py check C:\Games\MyGame --start-map 2 --x 5 --y 7 --expect-event Marta --talk Marta --screenshot after_talk --results C:\ClaudeDev\scratch\check1
```

A monster bump plus auto-battle (walk 5 tiles right into a touch-trigger monster, play the battle, then look at the result):

```powershell
python tools/vxace_smoke.py check C:\Games\MyGame --start-map 1 --x 10 --y 9 --step 6:5 --auto-battle attack --screenshot after_fight --results C:\ClaudeDev\scratch\check2
# report.md: INFO battle  troop=33 "Gold Ogre" result=win turns=6 frames=420 hp_before=[Vex 467/467] hp_after=[Vex 210/467] mode=attack
```

The same as a suite file, with a wait for a condition and a screenshot in the middle (`stage --suite`, then `run`):

```ruby
VXA_Smoke.script do
  auto_battle :attack
  goto 1, 10, 9, 6
  step 6, 5                                  # bumps the monster; the step ends when the battle starts
  wait_idle 1200                             # waits through the battle (auto_battle plays it), then for the map
  b = VXA_Smoke.battles.last
  check('won in 8 turns or fewer') { b[:result] == :win && b[:turns] <= 8 }
  talk 'Marta'
  wait_until(300, 'quest switch') { $game_switches[4] }
  screenshot 'quest_done'
  info 'gold', $game_party.gold.to_s
end
```

In a script `check`, `info` and `screenshot` are the same functions as before; `$game_*` are only touched inside blocks that run after the map is up (the script starts at the first `Scene_Map`).

## Report and exit codes

The JSON report holds status (`pass`, `failed`, `incomplete`, `timeout`, `integrity_failure`), mode, start, frames, nonce, runtime info, all records, counts, duration, process exit code, problems, script references, `screenshots` (file, label, size, bytes) and the two evidence flags. Markdown is a readable copy.

- Exit 0: header and footer valid, at least one record, no FAIL or ERROR.
- Exit 3: any FAIL, ERROR (including uncaught), timeout or incomplete/invalid report.
- Exit 2: configuration, freshness or integrity refusal (also bad options, existing outputs, changed staged scripts).

## Limits

- No real input device: only the virtual keys above. Mouse and text input are not simulated.
- Timing dependent: results change with frame counts, auto-confirm rate and machine load. Long cutscenes or `Wait` sequences can trip the runaway check; messages waiting for input do not (use `--auto-confirm` to advance them).
- Windows only for the real launch; the process runs as the current user with no sandbox. Only stage projects the user already trusts to run.
- One script-slot transaction per staged copy. Scripts that replace `SceneManager`, the first scene, `Graphics.update` or `Input` may conflict with or disable the harness; a harness that fails to start shows as a missing or incomplete results file.
- Battle test (`$BTEST`) does not use the boot override.
- v1.34 helpers are verified under host Ruby with RGSS3 stand-ins (unit level) and need a real engine run to confirm: the engine's `Zlib` availability (the stored-block fallback covers its absence), `Bitmap#get_pixel` speed, and the `Game_Event`/`Scene_Battle` internals the helpers read (`@interpreter`, `@starting`, the battle command windows). Scripts, `step` and `talk` use `Fiber`; a script that replaces the main loop or calls `Graphics.update` itself can break the scheduler.
- `auto_battle :attack` presses confirm on the party, actor and enemy windows (Fight, first command, first target); classes whose first command is not Attack, or battles with custom command windows, need a hand-written driver. `:win` and `:lose` change HP directly and prove nothing about difficulty; use `:attack` to measure a fight.
- Passing proves only that these frames ran without the recorded failures. It does not prove compatibility, save safety or correct gameplay.

## Native evidence (v1.8)

Staged through the full validator/reader/slot/planner/impact/copy chain against an editor-created project with two unrelated custom scripts, then launched with the real `Game.exe`. Playtest and normal runs passed suite checks (party, start map, virtual DOWN input moving the player three tiles); `--start save:1` loaded an existing save; a deliberate uncaught error was captured with exit 3 instead of a blocking dialog and its backtrace mapped to script names; the header reported Ruby 1.9.2 and the correct `$TEST`. Launched without the tool, the same copy stayed on its title screen and wrote no result file. The original project was unchanged.
