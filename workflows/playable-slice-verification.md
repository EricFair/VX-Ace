# Playable slice verification

Use this when moving from tooling tests to a small playable VX Ace feature. Serialization success does not establish gameplay success.

## Keep the artifacts distinct

Retain the source snapshot, a guarded delivery copy, and any instrumented test copy as separate directories. A test harness may arrange a rare condition, such as starting a battle at 1 HP, but record that arrangement and exclude it from the delivered game. Exercise the real interpreter, battle and save/load paths after arranging the condition; a stubbed result does not verify those paths.

Use fresh indexes and the normal copy patcher's byte gates for script replacements as well as native data edits. Keep proprietary default scripts, RTP art, saves and raw project reports local. Public evidence should describe scenarios and results without redistributing those files.

## Verify the state transitions

For a quest with acceptance, battle, recovery and reward, record state, inventory and currency at each boundary:

- before acceptance and on repeated acceptance;
- defeat: no objective completion, no victory item/reward, recovery sufficient for retry;
- retry: normal battle can start and complete after defeat;
- victory: grant the quest item once and advance to return state;
- turn-in: consume the item, pay the exact reward, enter completion state;
- repeated interaction, including after load: no additional reward.

Prefer native menu observations and native-created saves for verification. Read-only inspection of a private test save can corroborate counts, but never rewrite it with the project mutator. Preserve the evidence separately from the fresh-start delivery.

## Test persistence across a real restart

Save through the native game menu, close the playtest process, relaunch and Continue. Test both unfinished and completed states. Check objective text, inventory, currency, event selection and player position, rather than merely checking that loading did not raise an exception.

For runtime-generated database entries, recreate stable IDs before native save extraction. Verify the destination slot is free in the project snapshot. Save only durable state on the owning Game_* object; create windows and sprites with their scene lifecycle.

Runtime-generated map data is itself saved with Game_Map in the default engine. A script change does not automatically replace that saved data. If supporting previous prototype saves, inspect the exact native load lifecycle and choose an explicit migration or native version/map-reload strategy. Test that strategy with a save created before the change. Do not silently reset an active interpreter or event state merely to refresh visuals.

## Verify map visuals and movement together

Inspect the actual tileset names, graphic files and passage flags. B–E tile sheets use two eight-column halves; calculate a B tile as `(column / 8) * 128 + row * 8 + column % 8`, using integer division. A5 starts at 1536 with eight columns. Autotiles require their own shape/layout rules; do not treat them as ordinary 32px tiles.

Review the native rendered map for joins, missing tile halves, readable landmarks and HUD overlap. Walk the intended route and test walls, vegetation, event approach squares and return paths. A pretty screenshot does not prove passage, and static passage flags do not prove behavior with custom movement scripts or runtime events.

If scenery/events exist only at runtime, explain that clearly: they will not appear as authored editor map content. Do not imply this is a general map writer or a substitute for maintaining larger maps in the editor.

## Record the limits

List which scenarios ran in native VX Ace, which passed only automated checks, which use a harness, and which remain untested. Link each result to the corresponding local audit/build, and verify the original project inventory after testing. Publish skill/tool changes only after their relevant checks pass; do not call a playable prototype a complete engine-compatibility certification.
