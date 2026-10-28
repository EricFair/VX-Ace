# Guarded map shop — v1.15

Add one native Shop Processing block (command 302 with its 605 rows) to an existing map event. This connects goods you already appended (see [database append](database-append.md), [key-item append](key-item-append.md)) to gameplay through the existing Python disposable-copy workflow. It does not create items/weapons/armors, edit prices in the database, add a second shop, change the event page, graphic or trigger, or write save files.

## Source event

The event must already exist on the map and satisfy the same strict predicate as the [direct transfer](direct-map-transfer.md): exactly one page, stationary, unconditional, action-button trigger, blank graphic, fixed native fields. Its command list must be either

- **blank**: only the root terminator, or
- **dialogue**: exactly one literal Show Text block (a `101` header `["",0,0,2]`, one to four literal `401` lines, no escape codes) followed by the terminator — the shape [map event creation](map-event-creation.md) produces.

Anything else (conditions, touch/autorun triggers, movement, a graphic, an existing shop, other commands, a second block) is refused. Use `append_dialogue_event` to create a suitable event first when the map has none.

## Fresh read-only evidence

```powershell
python tools/vxace_map_shops.py PROJECT_INDEX --project PROJECT --map 1 --event 2 --output NEW_EXTERNAL_SNAPSHOT
```

`map-shop-snapshot.json` holds the native map, event and page-list SHA-256 values, the Items/Weapons/Armors array SHA-256 values (whole-array Marshal dump, the convention used by the enemies/troops/skills appends), the event shape (`blank`, `dialogue` or null), the dialogue lines, the valid ID range per goods type, `max_goods` and `append_supported` with an `unsupported_reason` when false. It also checks the complete native map and the three goods arrays against the index. A snapshot never authorizes mutation.

## Reviewed single-change specification

```json
{
  "title": "Reviewed shop",
  "changes": [{
    "kind": "map_shop",
    "locator": {"map_id": 1, "event_id": 2},
    "proposal": "Add the reviewed weapon and armor shop to the shopkeeper.",
    "mutation": {
      "action": "add_shop",
      "expected_map_sha256": "REPLACE_FROM_SNAPSHOT",
      "expected_event_sha256": "REPLACE_FROM_SNAPSHOT",
      "expected_list_sha256": "REPLACE_FROM_SNAPSHOT",
      "expected_items_sha256": "REPLACE_FROM_SNAPSHOT",
      "expected_weapons_sha256": "REPLACE_FROM_SNAPSHOT",
      "expected_armors_sha256": "REPLACE_FROM_SNAPSHOT",
      "goods": [
        {"type": "weapon", "id": 1, "price": null},
        {"type": "armor", "id": 2, "price": 250},
        {"type": "item", "id": 3, "price": 0}
      ],
      "purchase_only": false
    }
  }]
}
```

- `goods`: 1..32 entries, each exactly `type` (`item`, `weapon`, `armor`), `id` and `price`. IDs must exist as static non-nil entries in the matching native array (integers, never booleans or variables). No duplicate `(type, id)`.
- `price: null` uses the database price (price type 0, stored price 0). An integer 0..9999999 is a specified price (price type 1). A specified price of 0 makes the good free.
- `purchase_only: true` hides selling in that shop.

The first good becomes `302` `[goods_type, goods_id, price_type, price, purchase_only]` (goods_type 0 item, 1 weapon, 2 armor); each further good becomes a `605` row `[goods_type, goods_id, price_type, price]`. All rows are inserted at indent 0 immediately before the terminator, after the dialogue block if there is one. The Items/Weapons/Armors files are only read.

## Copy chain

```powershell
python tools/vxace_patch_planner.py PROJECT_INDEX --project PROJECT --spec reviewed-shop.json --output NEW_EXTERNAL_PLAN
python tools/vxace_copy_patcher.py PROJECT_INDEX --project PROJECT --spec reviewed-shop.json --copy NEW_DISPOSABLE_COPY --audit NEW_EXTERNAL_AUDIT --backend python
```

Exactly one shop per transaction, Python backend and post-copy re-indexing only; the shop cannot be combined with other changes to the same map or to Items, Weapons or Armors. The candidate verifier proves that the event list prefix and terminator are byte-identical, that the inserted commands equal the factory result, that nothing outside that one page list changed and that the goods arrays are still the approved bytes at the end. `System.version_id` advances once, as for [direct transfers](direct-map-transfer.md), so default older saves rebuild the edited event on load. Any failure removes the staged copy and keeps the audit.

## Recipe steps

`vxace_recipe.py` adds `append_dialogue_event` and `add_shop` (see [recipes](recipes.md)); `from_step` links a new weapon, armor or key item and a newly created event into the shop.

## Native evidence and limits

Inspect the event in VX Ace (`Shop Processing` plus the following goods rows), open the shop in play, buy and (unless purchase-only) sell, test an older save and a native save/restart. Custom shop scenes or price scripts can change what is displayed or charged; the tool cannot prove that. Specified prices are constants. Variable-driven shops, multiple shops per event, shops on events with graphics, conditions, several pages or extra logic, editing or removing an existing shop, and creating items or the event inside this operation remain deferred. No in-engine runtime run has been performed for this release; the independent Ruby-authored native fixture tests cover file-level behavior only.

## Native evidence (v1.15)

On a disposable copy of an editor-created project (prepared with one blank template event), a three-step [recipe](recipes.md) appended weapon 61, a Smith dialogue event and a shop selling that weapon at its database price plus item 1 at a specified 25. A smoke run started the event: the greeting showed, `Scene_Shop` opened and its goods were `[1, 61, 0, 0, false]` (the engine keeps the first command's five parameters) and `[0, 1, 1, 25]`. The original project was unchanged.
