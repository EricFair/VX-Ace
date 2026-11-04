# Guarded System fields edit (set_system_fields)

`set_system_fields` changes a bounded subset of `Data/System.rvdata2` in one transaction and nothing else. It is the way to make a new actor the starting party member, move the start position, rename the game or retitle a few terms. It never creates, deletes or reorders anything; every other System field (the other switch and variable slots, sounds, vehicles, elements, type lists, option flags, test settings, **`version_id`**) keeps its exact value, and every other file stays byte-identical.

## Snapshot and spec

```powershell
python tools/vxace_system_fields.py PROJECT_INDEX --project PROJECT --output NEW_EXTERNAL_SNAPSHOT [--start-map MAP_ID]
```

The read-only snapshot (`system-fields-snapshot.json`) returns `system_sha256`, the current title, currency unit, start, `version_id`, every editable term with its index, the actors (`actors_sha256`, names, current party), `mapinfos_sha256` and the map names, and with `--start-map` the hash, size and name of that map (`start_map`). A snapshot is not mutation permission.

The spec is a normal one-change patch spec with `kind: "system_fields"` and locator `{"table": "system"}`:

```json
{"title": "Retitle and re-party", "changes": [{
  "kind": "system_fields", "locator": {"table": "system"}, "proposal": "New title, Lena leads the starting party, start on map 2.",
  "mutation": {
    "action": "set_system_fields",
    "expected_system_sha256": "<system_sha256>",
    "game_title": "Hero Quest",
    "currency_unit": "Gold",
    "party_members": [11, 1],
    "expected_actors_sha256": "<actors_sha256>",
    "start": {"map_id": 2, "x": 4, "y": 5},
    "expected_mapinfos_sha256": "<mapinfos_sha256>",
    "expected_start_map_sha256": "<start_map.sha256>",
    "terms": {"params": {"0": "Vitality"}, "commands": {"0": "Battle"}}}}]}
```

## Fields

The mutation is `action`, `expected_system_sha256` and a non-empty subset of:

| Field | Rule |
|---|---|
| `game_title` | literal text, 1..100 characters |
| `currency_unit` | literal text, 1..10 characters |
| `party_members` | the starting party: 1..8 unique ids of existing actors. Needs `expected_actors_sha256` |
| `start` | exactly `{"map_id", "x", "y"}`: the map must be in MapInfos and its `MapNNN.rvdata2` must exist, `0 <= x < width`, `0 <= y < height`. Needs `expected_mapinfos_sha256` and `expected_start_map_sha256` |
| `switch_names` | Object `{"id": "name"}`: decimal id strings `"1"`..`"5000"` (no leading zero) of switches that exist in the fingerprinted System (ids run 1..len-1 of the native `switches` array), each a literal name of 0..32 characters; the empty string clears the name |
| `variable_names` | The same for the `variables` array |
| `terms` | object with keys `basic` (index 0..7), `params` (0..7), `etypes` (0..4), `commands` (0..22); each maps canonical decimal index strings (`"0"`, never `"00"` or `"-1"`) to new text of 1..32 characters |

Text is literal: control characters and backslash codes are refused. Any other key, any other System field and any hash that the chosen fields do not need is refused (only the needed `expected_*` hashes may appear), and a field that already has the requested value is refused as a no-op. A stale hash (System, Actors, MapInfos, start map) refuses without a copy. In an editor-saved project `RPG::System::Terms` holds `basic` 8, `params` 8, `etypes` 5 and `commands` 24 strings; index 23 of `commands` is an unused tail slot and not editable, and index 11 is an empty unused slot that is editable but meaningless.

Strings are written as new UTF-8 strings with the editor's `{E: true}` encoding flag; the party list is a new array of integers.

### Switch and variable names

In an editor-saved project `System.switches` and `System.variables` are arrays whose slot 0 is `nil` and whose slots 1..N are Ruby strings with ivar `{E: true}` (UTF-8), empty (`""`) when the editor shows the id as blank (a new project has 100 of each, all empty). A name edit replaces exactly the listed slots with new strings built the same way (an existing slot's encoding flag is reused); the array length, slot 0 and every other slot stay byte-identical, which the verifier checks slot by slot besides the usual deep-equality of all other System ivars. A name that already has the requested value is refused as a no-op, like every other field. The names are editor labels only: nothing reads them at run time, they are not stored in saves and they change no behavior. Impact and the recipe `plan` report them as `switch_names[11]: "" -> "Troll Killed"` rows. Staged events and common events warn about `unnamed switch N` / `unnamed variable N`; because each step reads the System left by the previous one (the simulated System in `plan`), naming the ids in an earlier step makes those warnings disappear for later steps.

## version_id and old saves

`version_id` is **not** advanced. `DataManager.reload_map_if_updated` only compares `$game_system.version_id` with `$data_system.version_id` to rebuild the current map of a loaded save (`Game_Map#setup`), which map edits need and System edits do not; advancing it would only reset the map state of every old save. This matches the other database-only operations (entry appends and common events never advance it). What each field does to existing saves (read from Game_Party, DataManager, Vocab and Scene_Title):

- `party_members`, `start`: read only when a **new game** starts (`Game_Party#setup_starting_members`, `DataManager.setup_new_game`). Old saves keep the party, map and position stored in the save.
- `game_title`: drawn only on the title screen (and only when the System "draw game title" option is on). The window caption comes from `Game.ini`, which this operation does not touch.
- `currency_unit` and `terms`: read live from `$data_system` (`Vocab`), so old saves show the new text on the next launch. Event texts that hard-code the old currency are not rewritten; long words can clip menu windows.

## Verification and impact

The Python copy backend checks the candidate: only the listed fields (and nothing else, including `version_id`) differ, the ivar set and order are unchanged, every other System ivar and every unrequested term is deep-equal, the result equals the approved factory result, and the project inventory shows only `Data/System.rvdata2` changed. The impact report lists old to new for each field and warns when the start position moves or the starting party changes (more than 4 members, new leader) and that terms and currency are read live. A passing run is evidence and not proof of runtime behavior: test a new game, an old save and a process restart.

## Recipes and limits

Recipe step: `{"type": "set_system_fields", "party_members": [{"from_step": 2}, 1], "start": {...}, ...}`; `from_step` is allowed only inside `party_members` and must name an earlier `append_entry` step on `actors`. The snapshot supplies every hash.

- One System edit per transaction, with no other change.
- Not editable: the switch and variable counts, sounds, vehicles, battle/title BGM, window tone, option flags, type lists, element names, test battlers, `version_id`.
- The start cell is range checked only; passability, events on the cell and the start-map BGM are not analysed.
- Scripts that overwrite `$data_system` or compare term strings are not analysed.

## Native evidence

A five-step recipe ran on an editor-created project, with `--rtp` pointing at the installed RTP. All postgates passed, the original was unchanged, and `version_id` was not advanced. The steps were:
1. a Hero Blade;
2. Lena, cloned from actor 1 with class 1 and level 3, Actor4 graphics, and the blade via `from_step`;
3. `set_system_fields` with title, currency, party `[Lena, 1]`, start 1:(4,5), and the param 0 and fight terms;
4. a blank event;
5. a Recruiter page adding actor 2.

In a real-engine new game:
- The party was Lena then Eric, and the player started on map 1 at 4,5 with Lena's Actor4 sprite.
- Lena had level 3, her nickname, class 1, the Hero Blade, and both graphics.
- `.game_title`, `Vocab.currency_unit`, `Vocab.param(0)` and `Vocab.fight` returned the new text.
- The Recruiter added actor 2.

An existing save loaded with its own party (Eric only) and showed the new currency and terms. The title screen was not drawn in the smoke run (it starts past the title), so check it in a normal launch.
