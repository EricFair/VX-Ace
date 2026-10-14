# Oakfall Village example

`quest.rb` is original RGSS3 example code, tested in a private disposable VX Ace project. It provides an elder quest, a native two-Slime battle with loss/retry, a key item, a one-time reward, an objective window and simple runtime village scenery. No proprietary default scripts, RTP images/audio, project database or saves are included.

This is a reviewed prototype example, not an installer for arbitrary games. Its observed seed requirements are:

- map 1 is a blank 17×13 map with exactly one blank event, ID 1;
- the new-game player starts at (8,6), facing the elder at (8,7);
- event IDs 2 and 3 are free;
- item 1 is Potion, the item array has 17 entries and slot 17 is free;
- troop 1 is the seed's two-Slime encounter;
- tileset 2 is Exterior, with the default installed Outside_* RTP sheets and native flags;
- the default classes and lifecycle methods wrapped in this script have been inspected and there are no overlapping custom hooks in the seed;
- Main contains exactly one `rgss_main { SceneManager.run }` anchor.

Verify these against a fresh project index and use the guarded script replacement workflow to place this code before that anchor on a disposable copy. Run the whole-project validator and immediate target byte gate first. Do not paste it into an unrelated working project or assume its IDs are available there.

Open the copied project in VX Ace, F12, New Game. Arrows move; Enter/Space/Z confirm; Esc/X open the menu. Talk to the elder, follow the northeast path to the crystal, defeat its guardian, then return the relic. New Game grants three Potions; turn-in grants 100 gold and two more Potions. Battle rewards are separate.

## Ownership and persistence

Quest stage belongs to Game_System. The item definition is recreated at the same free ID during database loading, before native save extraction. The window is transient scene state. Runtime native events replace the seed's blank event and use the two verified free event IDs.

Scenery is runtime RPG::Map/Table data, using Exterior passage flags. On load, only this prototype map's scenery and tileset are regenerated; the saved quest state, player position, runtime events and interpreter are retained. This narrowly supports this example's earlier prototype saves, not general save migration. These maps/events appear during Playtest, not as authored map editor content. Cottage doors are decorative and do not transfer indoors.

## Native evidence

On 15 October 2026, the actual installed VX Ace F12 runtime verified:

- cottages, trees, flowers, paved square and shrine path rendering;
- walking from shrine to elder across the path and square;
- loading an earlier completed-quest save into the scenery build, preserving completion, 110 gold and five Potions; elder repeat dialogue prevented another reward;
- defeat in a separate private harness with one-time 1 HP setup: full recovery, quest stage 1, no relic, no gold;
- normal retry victory after recovery: stage 2, one relic, 10 battle gold, three Potions;
- turn-in after retry: stage 3, no relic, 110 gold, five Potions;
- native saving, closing the process, relaunching and loading the newly created scenery save: village, completion objective and position (8,6) restored.

The artificial injury, shortcut starting position and private observation log belong only to the test harness and are absent from `quest.rb`. All 16 Data files in the non-harness scenery build passed byte-identical validation and all 126 script slots passed host-Ruby syntax diagnostics. The fresh delivery's 16 Data files matched that tested non-harness build byte-for-byte. The user's original project inventory remained unchanged.

This evidence covers the small default seed and the stated paths. It does not certify arbitrary scripts, imported saves, map transfers or a general-purpose map writer. Follow [playable slice verification](../../workflows/playable-slice-verification.md) for further features.
