# RTP character sprites (stock VX Ace RTP, Graphics/Characters)

A text catalogue of the 48 stock character sheets, so a sprite can be picked without opening each image. Machine-readable copy: `tools/data/rtp_sprites.json`. Only descriptions ship here, never images.

- Index `0..3` is the top row of a sheet, `4..7` the bottom row, left to right. A `$` sheet is one character (index 0). A `!` sheet is an object sheet (no upward shift when drawn).
- Descriptions are brief and approximate (hair colour and outfit for people). Several of the Behavior, Damage and Insane sheets are pose variants and are described per sheet only.
- A recipe page can use `"graphic": {"sprite": "grey rats"}` instead of sheet and index; see below.

## Picking a sprite in a recipe

Any recipe `graphic` object may be `{"sprite": "words"}` (optionally with `"direction"` 2/4/6/8, default 2, and `"pattern"` 0..2, default 1). The words are matched against the catalogue descriptions (and sheet names), case-insensitively; every word must appear. When exactly one sprite matches the recipe resolves it to `character_name` and `character_index`. If none or several match, the recipe is refused and the candidates are listed (up to 10). An exact `"Sheet:index"` such as `"Monster3:4"` always resolves. `plan` shows the resolved sheet and index.

```json
{"type": "add_monster", "map_id": 4, "x": 6, "y": 6, "name": "Rat", "troop": 34, "graphic": {"sprite": "grey rats"}}
```

Lookup from the command line: `python tools/vxace_rtp_sprites.py grey rats` (or `--list`, `--sheet Monster3`).

## Tiles

The tile notes (A5 floors, walls and paths; B landmarks) for the stock Exterior, Interior and Dungeon tilesets are in [map-layouts.md](map-layouts.md#presets-stock-rtp-tilesets-only). They were chosen from the A5 and B sheet images.

## Sheets

### `!$Gate1` (object, single, 288x256)

gate, 3 columns x 4 rows of frames (closed to open); use as a single-character gate.

0: wooden arched double gate that swings open to a dark passage

### `!$Gate2` (object, single, 288x256)

gate, 3 columns x 4 rows of frames.

0: grey stone and iron portcullis style gate that opens to a dark passage

### `!Chest` (object, 384x256)

treasure chests; row of frames per direction/open state.

| index | description |
|---|---|
| 0 | red wooden chest |
| 1 | beige wooden chest |
| 2 | green wooden chest |
| 3 | blue wooden chest |
| 4 | gold-trimmed brown chest |
| 5 | steel blue iron chest |
| 6 | gold ornate chest |
| 7 | small red box chest |

### `!Crystal` (object, 384x512)

glowing crystals (384x512, tall cells).

| index | description |
|---|---|
| 0 | blue crystal |
| 1 | green crystal |
| 2 | red pink crystal |
| 3 | violet crystal |
| 4 | pale blue crystal variant |
| 5 | pale green crystal variant |
| 6 | pale pink crystal variant |
| 7 | pale violet crystal variant |

### `!Door1` (object, 384x256)

doors that open when the page graphic steps through the frames.

| index | description |
|---|---|
| 0 | brown wooden plank door |
| 1 | brown wooden plank door variant |
| 2 | blue grey arched steel door |
| 3 | blue grey arched steel door variant |
| 4 | small brown panelled door |
| 5 | cream cloth curtain door |
| 6 | grey carved stone door |
| 7 | black iron fence gate |

### `!Door2` (object, 384x256)

doors and gates (barred, metal, vault, fence).

| index | description |
|---|---|
| 0 | iron barred cell door |
| 1 | coloured metal arched door (grey tan red green blue purple) |
| 2 | coloured metal arched door lower row |
| 3 | round vault door with glowing gem |
| 4 | carved brown wooden gate |
| 5 | wooden fence post gate |
| 6 | green glass crystal panel door |
| 7 | black iron spike fence gate |

### `!Door3` (object, 384x512)

tall doors (384x512, tall cells).

| index | description |
|---|---|
| 0 | tall brown wooden plank door |
| 1 | tall brown wooden plank door variant |
| 2 | tall blue grey arched steel door |
| 3 | tall blue grey arched door variant |
| 4 | tall brown panelled door |
| 5 | tall cream cloth curtain door |
| 6 | tall grey carved stone door |
| 7 | tall black iron fence gate |

### `!Flame` (object, 384x256)

flames, lamps and light effects.

| index | description |
|---|---|
| 0 | lamps with orange blue and white flames |
| 1 | lanterns and candle light |
| 2 | campfire with logs |
| 3 | large orange bonfire |
| 4 | small orange torch flame |
| 5 | small blue flame |
| 6 | white sparkle glints |
| 7 | smoke puffs and star bursts |

### `!Hexagram` (object, 384x256)

magic circles (hexagrams).

| index | description |
|---|---|
| 0 | light blue magic circle |
| 1 | green magic circle |
| 2 | pink red magic circle |
| 3 | yellow magic circle |
| 4 | black magic circle |
| 5 | white hexagram |
| 6 | pale violet hexagram |
| 7 | blue violet hexagram |

### `!Other1` (object, 384x256)

rocks, traps and orbs.

| index | description |
|---|---|
| 0 | brown boulder |
| 1 | grey stone boulder |
| 2 | snowball |
| 3 | black sphere ball |
| 4 | floor pits and spike trap |
| 5 | faint footprints ripples |
| 6 | small coloured orbs (red blue green purple) |
| 7 | crystal orbs on stands (red blue green purple) |

### `!Other2` (object, 384x512)

weather and fire effects (384x512, tall cells).

| index | description |
|---|---|
| 0 | icy frost wind streaks |
| 1 | white wind streaks |
| 2 | orange fire streaks |
| 3 | yellow fire streaks |
| 4 | white wind swirl dust |
| 5 | ghostly white ice pillars |
| 6 | orange fire columns |
| 7 | coloured brazier torches (blue green orange) |

### `!Other3` (object, 384x512)

small props and furniture (384x512, tall cells); hard to tell apart at 1x, check the sheet image.

| index | description |
|---|---|
| 0 | bread loaves and baked food |
| 1 | bottles vials and small tools |
| 2 | plates and dishes |
| 3 | potted plants and flowers |
| 4 | stone piles and grave markers |
| 5 | swords and crosses (grave markers) |
| 6 | grey double doors and cabinets |
| 7 | books shovel and pick tools |

### `!Switch1` (object, 384x256)

levers (top row) and floor buttons (bottom row).

| index | description |
|---|---|
| 0 | grey lever with red knob |
| 1 | brown lever with red knob |
| 2 | grey lever with green knob |
| 3 | green lever |
| 4 | red floor button |
| 5 | yellow floor button |
| 6 | green floor button |
| 7 | blue floor button |

### `!Switch2` (object, 384x256)

wall switches (top row) and square buttons (bottom row).

| index | description |
|---|---|
| 0 | grey wall switch red light |
| 1 | grey wall switch yellow light |
| 2 | grey wall switch green light |
| 3 | grey wall switch blue light |
| 4 | red square button |
| 5 | yellow square button |
| 6 | green square button |
| 7 | blue square button |

### `$BigMonster1` (single, 192x256)

one big monster per DIRECTION row: pick the monster with the direction value (2 down, 4 left, 6 right, 8 up).

Direction picks the monster: 2 = red winged lion demon (manticore); 4 = spiked dark armour knight; 6 = dark horned beast demon; 8 = blue serpent naga woman.

### `$BigMonster2` (single, 240x320)

one big monster per DIRECTION row: pick the monster with the direction value (2 down, 4 left, 6 right, 8 up).

Direction picks the monster: 2 = blue winged gargoyle demon; 4 = green winged dragon; 6 = red many-armed demon lord; 8 = green ogre troll.

### `$Coffin` (single, 96x128)

coffin; the direction rows give four tilt states.

0: red coffin

### `Actor1` (normal, 384x256)

eight character cast members; the guesses below go by hair colour and outfit.

| index | description |
|---|---|
| 0 | orange haired young man in a red tunic |
| 1 | blond hero with a red top |
| 2 | green haired adventurer |
| 3 | teal haired young man |
| 4 | light brown haired girl in white |
| 5 | brown haired man in green and orange |
| 6 | dark haired fighter in red brown |
| 7 | silver haired old man in tan robe |

### `Actor2` (normal, 384x256)

eight character cast members; the guesses below go by hair colour and outfit.

| index | description |
|---|---|
| 0 | blue haired knight in blue |
| 1 | green haired adventurer in green |
| 2 | teal capped fighter in blue |
| 3 | blond in a red beret |
| 4 | silver white haired mage in blue |
| 5 | pink haired girl in pink |
| 6 | brown clad rogue in brown hat |
| 7 | witch in a dark purple pointed hat |

### `Actor3` (normal, 384x256)

eight character cast members; the guesses below go by hair colour and outfit.

| index | description |
|---|---|
| 0 | red haired swordsman |
| 1 | dark teal haired girl |
| 2 | purple haired man |
| 3 | pinkish white haired girl with ornaments |
| 4 | blond man in olive |
| 5 | long blond haired woman |
| 6 | grey helmeted armoured knight |
| 7 | pink haired girl |

### `Actor4` (normal, 384x256)

eight character cast members; the guesses below go by hair colour and outfit.

| index | description |
|---|---|
| 0 | silver haired armoured knight in blue |
| 1 | pink haired girl with twin tails |
| 2 | long blond haired girl |
| 3 | green haired girl with horn headgear |
| 4 | orange spiky haired man with blue cape |
| 5 | brown pink haired girl |
| 6 | teal haired man |
| 7 | black haired man in red |

### `Actor5` (normal, 384x256)

eight character cast members; the guesses below go by hair colour and outfit.

| index | description |
|---|---|
| 0 | brown haired young man in leather |
| 1 | grey haired man in a green cloak |
| 2 | dark blue haired man in green cloak |
| 3 | blond spiky haired hero |
| 4 | brown haired girl in a white hood (nun) |
| 5 | white hooded priest |
| 6 | red haired woman in red robes |
| 7 | blond princess in white and gold |

### `Animal` (normal, 384x256)

farm and wild animals (and butterflies).

| index | description |
|---|---|
| 0 | pink pig |
| 1 | white cat |
| 2 | white chicken hen |
| 3 | white sheep |
| 4 | grey white cow |
| 5 | brown horse |
| 6 | grey wolf |
| 7 | blue butterflies |

### `Behavior1` (normal, 384x256)

cast poses incl. frozen in ice and petrified grey statues; indices are not separately described.

All indices: cast pose variants incl. frozen in blue ice and petrified grey.

### `Behavior2` (normal, 384x256)

cast poses incl. frozen in ice and petrified grey; indices are not separately described.

All indices: cast pose variants incl. frozen in ice and petrified grey.

### `Behavior3` (normal, 384x256)

cast poses with sparkle auras; indices are not separately described.

All indices: cast pose variants incl. sparkle and aura effects.

### `Behavior4` (normal, 384x256)

cast poses with glowing ghost silhouettes; indices are not separately described.

All indices: cast pose variants incl. glowing white ghost silhouettes.

### `Damage1` (normal, 384x256)

hurt or collapsed poses of cast members; indices are not separately described.

All indices: cast members in hurt kneeling poses, light clothes.

### `Damage2` (normal, 384x256)

hurt or collapsed poses of cast members; indices are not separately described.

All indices: cast members in hurt kneeling poses, hooded and armoured.

### `Damage3` (normal, 384x256)

hurt poses of monsters and villains; indices are not separately described.

All indices: monster and villain hurt poses (skeleton, demons, dark knights).

### `Damage4` (normal, 384x256)

hurt poses of costume cast; indices are not separately described.

All indices: holiday costume cast hurt poses (santa, reindeer).

### `Evil` (normal, 384x256)

villains and dark armour.

| index | description |
|---|---|
| 0 | green haired man in red black |
| 1 | white turbaned desert man |
| 2 | hooded dark grey cloak figure |
| 3 | hooded brown black cloak figure |
| 4 | pale pink long haired dark lord |
| 5 | gold masked armour |
| 6 | black and gold dark knight |
| 7 | olive and black spiked armour |

### `Insane1` (normal, 384x256)

crazed faces of townsfolk; indices are not separately described.

All indices: crazed expression townspeople (children, bald man, elderly).

### `Insane2` (normal, 384x256)

crazed faces of robed folk; indices are not separately described.

All indices: crazed expression robed and hooded elders.

### `Monster1` (normal, 384x256)

undead, fire and dark monsters.

| index | description |
|---|---|
| 0 | black shadow ghost with red eyes |
| 1 | white skeleton with red cape |
| 2 | bald tan skinned goblin ogre |
| 3 | dark teal winged gargoyle bat demon |
| 4 | flame wrapped fire spirit |
| 5 | pale ghost woman with white hair |
| 6 | dark blue hooded reaper wizard |
| 7 | orange red armoured warrior |

### `Monster2` (normal, 384x256)

plants, dragons and slimes.

| index | description |
|---|---|
| 0 | pink flower plant |
| 1 | green winged lizard dragon |
| 2 | blue slime |
| 3 | pink white haired harpy fairy |
| 4 | blue flower plant |
| 5 | red lizard dragon |
| 6 | green slime |
| 7 | green haired lamia harpy |

### `Monster3` (normal, 384x256)

bats, rats, bugs and sea creatures.

| index | description |
|---|---|
| 0 | purple bats |
| 1 | red blob with a white eye |
| 2 | yellow wasp bee |
| 3 | lilac jellyfish ghost |
| 4 | grey rats |
| 5 | blue drake fishman |
| 6 | red scorpion lobster |
| 7 | brown green spiders crabs |

### `People1` (normal, 384x256)

eight townsfolk; the guesses below go by hair colour and outfit.

| index | description |
|---|---|
| 0 | orange haired boy in green |
| 1 | orange pigtail girl |
| 2 | green haired boy |
| 3 | long brown haired girl |
| 4 | brown haired man in olive |
| 5 | girl in a white wimple (nun) |
| 6 | bald old man |
| 7 | white haired elder in orange and white |

### `People2` (normal, 384x256)

eight townsfolk; the guesses below go by hair colour and outfit.

| index | description |
|---|---|
| 0 | grey haired old man |
| 1 | dark blue hooded cloak villager |
| 2 | light blue hooded elder |
| 3 | purple turbaned merchant |
| 4 | bald tan villager man |
| 5 | blue grey long haired elder woman |
| 6 | white blue haired woman with headdress |
| 7 | dark blue haired woman |

### `People3` (normal, 384x256)

eight townsfolk; the guesses below go by hair colour and outfit.

| index | description |
|---|---|
| 0 | teal haired girl |
| 1 | blue capped guard |
| 2 | grey hooded priestess |
| 3 | blue capped grey guard |
| 4 | red haired boy with bandana |
| 5 | dark brown haired maid |
| 6 | green hooded elf peasant |
| 7 | blond girl with big ribbons |

### `People4` (normal, 384x256)

eight townsfolk; the guesses below go by hair colour and outfit.

| index | description |
|---|---|
| 0 | white haired crowned princess |
| 1 | orange curly haired girl |
| 2 | green haired noble boy |
| 3 | blond princess in red and gold |
| 4 | brown haired man |
| 5 | grey haired old noble |
| 6 | steel plate armour knight |
| 7 | dark steel armour knight |

### `People5` (normal, 384x256)

eight townsfolk; the guesses below go by hair colour and outfit.

| index | description |
|---|---|
| 0 | red haired boy in olive |
| 1 | blond pigtail girl |
| 2 | red haired man in green |
| 3 | teal haired man with yellow |
| 4 | grey stubble man |
| 5 | white haired old woman |
| 6 | bald monk man |
| 7 | headband elf in light green |

### `People6` (normal, 384x256)

eight townsfolk; the guesses below go by hair colour and outfit.

| index | description |
|---|---|
| 0 | pink haired girl in pastel |
| 1 | brown haired boy in green |
| 2 | blue haired child in grey blue |
| 3 | pale blond girl in lavender |
| 4 | orange haired girl in pink dress |
| 5 | blond girl in orange |
| 6 | yellow haired boy in orange |
| 7 | brown haired man in red |

### `People7` (normal, 384x256)

eight townsfolk; the guesses below go by hair colour and outfit.

| index | description |
|---|---|
| 0 | blue haired boy in blue |
| 1 | salmon haired man in orange |
| 2 | purple haired man |
| 3 | pale lavender haired woman |
| 4 | pink haired girl |
| 5 | blond boy in blue |
| 6 | green haired man in teal |
| 7 | brown haired man in orange |

### `People8` (normal, 384x256)

eight townsfolk; the guesses below go by hair colour and outfit.

| index | description |
|---|---|
| 0 | dark blue haired man in blue |
| 1 | white haired man in teal |
| 2 | brown haired man in orange |
| 3 | red haired girl in pink |
| 4 | santa claus red suit white beard |
| 5 | reindeer costume in brown |
| 6 | blond girl in red santa dress |
| 7 | red santa hooded cloak |

### `Riding` (normal, 576x384)

mounted riders; frames are 48x48 so the sheet is 576x384.

| index | description |
|---|---|
| 0 | armoured knight on a grey horse |
| 1 | dark rider on a brown horse |
| 2 | grey armoured rider on a horse |
| 3 | blue armoured rider on a horse |
| 4 | red plumed soldier rider |
| 5 | gold armoured rider |
| 6 | gold armoured rider variant |
| 7 | black armoured rider |

### `Spiritual` (normal, 384x256)

spirits and angels.

| index | description |
|---|---|
| 0 | orange fire haired spirit woman |
| 1 | blue haired water spirit in blue gown |
| 2 | silver white wind spirit woman |
| 3 | green haired earth spirit woman |
| 4 | golden haired fairy |
| 5 | blond woman in white and gold (angel) |
| 6 | pale gold angel with blue sash |
| 7 | bearded blond sage |

### `Vehicle` (normal, 384x256)

vehicles.

| index | description |
|---|---|
| 0 | small brown rowboat |
| 1 | large white sailed ship |
| 2 | green balloon airship |
| 3 | white zeppelin airship |
| 4 | brown horse |
| 5 | white covered wagon |
| 6 | empty wooden minecart |
| 7 | minecart loaded with ore |

