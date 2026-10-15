# Optional PNG header and layout observations — v0.17

Use this to review graphics sizes before native playtesting. These read-only checks extend the [asset reference audit](asset-audit.md), retaining its fresh-index, external-report and explicit RTP rules.

```powershell
python tools/vxace_asset_audit.py PROJECT_INDEX --project PROJECT --rtp "C:/Explicit/Path/To/rtp" --image-headers --output NEW_EXTERNAL_REPORT
```

The bundled master settings enable `image_headers: true` inside the existing asset stage. Older settings that omit it retain presence-only behavior. The flag must be boolean and requires `asset_audit: true`. The standalone audit remains opt-in.

## Observations and findings

For each unambiguous matched PNG, read at most 33 bytes: the signature and first IHDR chunk. Validate its length/type, CRC, legal dimensions and header fields, then report width, height, bit depth, color type and interlace. No pixels are allocated or decoded. Header byte digests are rechecked before reporting; descriptor/path metadata and the existing asset catalog snapshots must also remain unchanged. These observations are not a filesystem lock or OS security sandbox.

`image_header.status` is `header_observed`, `invalid_png_header` or `unsupported_header_format`. JPG/JPEG may resolve as present, but their headers remain explicitly unsupported here. Audio, unresolved names and ambiguous graphic candidates are not opened as PNGs. Presence statuses remain separate from header/layout findings.

Default-engine character layouts divide the bitmap into 12 columns/eight rows, or three columns/four rows for single-character references. Prefix handling follows the default RGSS3 script's first-two-character test: `$Hero`, `!$Door` and `$!Door` select the single-character grid. `nested/$Hero` does not; the engine examines the full reference string. A `character_grid_remainder` finding reports integer frame dimensions when the image is too small or divides unevenly. Frame sizes may vary; this does not enforce 32-pixel characters.

For native tileset slots, compare against standard full-sheet dimensions:

| Slot | Standard dimensions |
| --- | --- |
| A1 / A2 | 512 × 384 |
| A3 | 512 × 256 |
| A4 | 512 × 480 |
| A5 | 256 × 512 |
| B / C / D / E | 512 × 512 |

A `nonstandard_tileset_dimensions` finding is advisory. A partial sheet may intentionally cover only used tiles; these checks do not establish which source rectangles the game needs. All referenced roles are retained even when the same image fills several slots and only three provenance samples are displayed.

Any invalid/unsupported header or nonstandard layout makes the audit exit `3` for review, while source/index/catalog changes still refuse the report. Mutation readiness remains a separate byte gate.

## Limits and evidence

A header-only file can pass these observations despite having no valid pixels, IDAT or IEND. Later chunks, full-image CRCs, decompression, alpha behavior, engine format support, memory limits, face/animation atlas coverage and custom script layouts are not validated. `header_observed` and `standard_layout` never mean “playable image.” Native testing remains required.

The header fields/checksum follow the [W3C PNG specification](https://www.w3.org/TR/PNG-Chunks). Character division/prefix behavior was checked against legally installed default RGSS3 scripts; those proprietary scripts are not distributed here.

Sixteen focused tests cover malformed/truncated headers, CRC/field/range errors, legal palette/interlace headers, bounded reads, prefix semantics, uneven grids, all nine standard tileset roles, unsupported formats, opt-in behavior, same-metadata header changes, provenance limits and source immutability. Two master tests cover flags/dependencies and older settings.

On a private disposable editor-produced project, native `Bitmap`/`Sprite_Character` observations matched four authored PNG cases: ordinary 13×9 → 1×1 frames; `$` 96×128 → 32×32; `!$` 96×128 → 32×32; nested `.../$` 96×128 → 8×16. Native A1, A2 and B measurements also matched. The deliberately uneven referenced actor sheet produced exactly one grid warning. Guarded staging and 16/16 post-copy byte gates passed. Separately, the private Oakfall index resolved 290 assets, observed 155 PNG headers and found 25 standard layouts. Raw projects, RTP, harnesses and reports remain private.
