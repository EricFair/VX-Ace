# Asset-bound character graphics on new dialogue events — v0.27

The [stationary dialogue append](map-event-creation.md) still requires an exact blank native template. An optional character graphic may now be supplied for the **new detached record only**. Existing event/page graphics, tile graphics, movement routes, copied logic and arbitrary field writes are outside this operation.

## Capture the proposed asset

```powershell
python tools/vxace_map_events.py PROJECT_INDEX --project PROJECT --map MAP_ID --template-event EXISTING_ID --character EXACT_BASENAME --character-index INDEX --direction 2 --pattern 1 --rtp EXPLICIT_RTP_ROOT --output NEW_PRIVATE_SNAPSHOT
```

Use an exact basename without path/extension, from the actual project or explicit separate read-only RTP. Project assets take precedence. Missing, ambiguous, case-mismatched, linked or non-PNG resolutions refuse; no asset discovery, installation or copying is performed. Output directories must be outside source/index/RTP.

Full selected file SHA-256, regular-file/descriptor/path stability,32MiB bounds and valid bounded PNG IHDR/CRC are required. Default native character-grid semantics use the first two reference characters: a leading `!` or `$` with `$` among those two selects3×4 single-character frames; otherwise12×8 eight-character frames. `!` as the first character retains native object-character positioning/bush semantics. A sheet must divide exactly into the selected grid with each frame1–256 pixels in each dimension. Single-character sheets require index0; ordinary sheets allow0–7. Direction is2/4/6/8 and pattern0–2.

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

## Verification

Ten new synthetic tests cover native fields, full copy/audit, low-level context refusal, missing/corrupt/ambiguous/case/dimension/byte bounds, optional schema/stale hash, default single/object prefixes, explicit RTP/project precedence, read-only snapshot and final-asset-change rollback with source unchanged. All388 executable tests and all seven read-only master stages passed locally.

Private native copies verified an ordinary eight-character sheet, a `$` single-character sheet and a `!` object sheet. The editor displayed the selected NPC; native action-button interaction turned it toward the player and showed both dialogue lines. Independent authored native assertions verified actual bitmap/frame sizes and positioning: the single sheet used192×256 pixels with64×64 frames and a four-pixel shift; the object sheet used384×256 with32×32 frames, native object-character status and zero shift. Frame rectangles remained inside their bitmaps.

Each native case loaded the unchanged older save, reconstructed the new event once, completed dialogue, saved once and loaded that save in a different Game process with the same event/state and no extra map setup or save rewrite. Bound asset hashes, existing events/map fields, other Data and baseline sources remained unchanged. These cases cover the inspected default engine/resources; custom rendering/map/save hooks still need project-specific review and native testing. Proprietary images/projects/saves/raw reports remain private.
