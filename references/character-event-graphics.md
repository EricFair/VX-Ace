# Asset-bound character graphics on new dialogue events

The [stationary dialogue append](map-event-creation.md) still requires an exact blank native template. An optional character graphic may be supplied for the **new detached record only**. Existing event/page graphics, tile graphics, movement routes, copied logic and arbitrary field writes are outside this operation.

## Capture the proposed asset

```powershell
python tools/vxace_map_events.py PROJECT_INDEX --project PROJECT --map MAP_ID --template-event EXISTING_ID --character EXACT_BASENAME --character-index INDEX --direction 2 --pattern 1 --rtp EXPLICIT_RTP_ROOT --output NEW_PRIVATE_SNAPSHOT
```

Use an exact basename without path/extension, from the actual project or explicit separate read-only RTP. Project assets take precedence. Missing, ambiguous, case-mismatched, linked or non-PNG resolutions refuse; no asset discovery, installation or copying is performed. Output directories must be outside source/index/RTP.

Full selected file SHA-256, regular-file/descriptor/path stability, 32 MiB bounds and valid bounded PNG IHDR/CRC are required. Default native character-grid semantics use the first two reference characters: a leading `!` or `$` with `$` among those two selects 3×4 single-character frames; otherwise 12×8 eight-character frames. `!` as the first character retains native object-character positioning/bush semantics. A sheet must divide exactly into the selected grid with each frame 1–256 pixels in each dimension. Single-character sheets require index 0; ordinary sheets allow 0–7. Direction is 2/4/6/8 and pattern 0–2.

These are header/layout and exact-byte observations, **not full decoding or native rendering proof**. Inspect the selected character, direction, frame, positioning and animation in actual VX Ace. Custom rendering scripts can change these semantics.

## Optional mutation fields

Keep every base dialogue-append field and add both:

```python
mutation["graphic"] = snapshot["proposed_graphic"]
mutation["expected_asset"] = snapshot["asset"]
```

Either both fields appear or neither does. The graphic dictionary has exactly `character_name`, `character_index`, `direction`, `pattern`. Asset binding includes exact name/origin/path/SHA/dimensions/layout/frame size/object-character flag. Do not construct these values from guesses or substitute another file after review.

Stage through the normal planner and Python copy patcher, adding `--rtp EXPLICIT_RTP_ROOT` only when required. Low-level graphical writes require the actual canonical map source path and explicit asset context; adjacent actual project/RTP files are independently rechecked. Candidate verification reconstructs the approved new record from the exact template and real bound asset. A final asset-resolution/hash recheck must pass or the whole copy is rolled back. Existing source/assets stay untouched. Blank dialogue append remains supported with its original schema.

All base full-map/template/identity/cell/command/version/impact/re-index/semantic/post-project gates still apply. This does not authorize modifying an existing NPC, adding a resource or changing asset files.

## Options and priority

The recipe step `append_dialogue_event` exposes the graphic (`graphic`, bound through the snapshot above and `--rtp`) and an optional `options` object (a non-empty subset of `walk_anime`, `step_anime`, `direction_fix`, `through` and `priority` = `below`/`same`/`above`, allowed only with a graphic; on the mutation it appears as `options` next to `graphic` and `expected_asset`). A dialogue event with a graphic is stored with priority **same** unless `options.priority` says otherwise, so the player bumps into it; a dialogue event without a graphic keeps the template page's priority. The remaining page fields still come from the blank template. `add_shop` works on such an event (see [shops and inns](shops-and-inns.md)).

## Verification

The tests cover the native fields, full copy and audit, missing/corrupt/ambiguous assets, stale hashes, RTP/project precedence and rollback when the asset changes late.

Native copies verified an ordinary eight-character sheet, a `$` single-character sheet and a `!` object sheet. The editor displayed the selected NPC; action-button interaction turned it toward the player and showed both dialogue lines. Native assertions verified the actual bitmap and frame sizes and positioning (single sheet 192×256 with 64×64 frames and a four-pixel shift; object sheet 384×256 with 32×32 frames and zero shift).

Each case loaded the unchanged older save, reconstructed the new event once, saved, and loaded that save in a different Game process with the same state. Bound asset hashes, existing events and other Data stayed unchanged. These cases cover the default engine; custom rendering/map/save hooks need project-specific review and native testing.
