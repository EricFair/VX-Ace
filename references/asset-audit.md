# Read-only graphics/audio references — v0.15

Use this when checking missing assets or filename casing from a fresh project index. It searches the project first, then an optional explicitly supplied unpacked RTP root. It never installs, copies, renames or repairs assets.

```powershell
python tools/vxace_asset_audit.py PROJECT_INDEX --project PROJECT --output NEW_EXTERNAL_REPORT
python tools/vxace_asset_audit.py PROJECT_INDEX --project PROJECT --output NEW_EXTERNAL_REPORT --rtp "C:/Explicit/Path/To/rtp"
python tools/vxace_master.py PROJECT --output NEW_EXTERNAL_REPORT --rtp "C:/Explicit/Path/To/rtp"
```

The RTP root must be a separate directory containing Graphics/ or Audio/. A missing RTP argument leaves unresolved references uncertain; it does not turn a normal RTP-based game into hundreds of proven missing-file errors. Do not guess RTP availability from a registry entry, a successful file name match elsewhere on disk or an installed editor alone. Supply the actual directory when it is known. The standalone command and master require a new external report directory outside the game, index and RTP, with fresh source/index evidence. v0.16 adds explicit RTP-output refusal before report creation.

## What is checked

Native indexed references include actor/vehicle/event characters, actor/message faces, enemy/system battlers, animation sheets and nested sound effects, tileset sheets, map/system battlebacks, title layers, parallaxes and native BGM/BGS/ME/SE objects. Recognized event parameter positions include Show Text faces, Show Picture names, change battleback/parallax, actor/vehicle graphics and movement-route character changes. The tool follows normalized data without executing scripts. Inactive database/event content is included: this is a reference inventory, not a reachability judgment.

Project files take precedence over RTP, including a local filename case mismatch. Report paths retain actual casing of folders, basenames and extensions. Nested relative asset names and dotted basenames are supported. Unsafe names, opaque strings, invalid recognized command parameters, linked paths, incomplete indexes and budget exhaustion cannot become a clean result.

Presence candidates include graphics PNG/JPG/JPEG and audio OGG/WAV/MP3/MID/MIDI. Common alternative formats such as WEBP/BMP/WMA remain `unverified_extension`; their presence is not treated as proof of engine support. Text metadata sidecars are excluded from competing image candidates. This list is the audit's search coverage, not a full statement of the engine's supported codecs.

## Result states

| State | Meaning |
| --- | --- |
| `found` | One searched candidate exists with matching case, in the project or supplied RTP |
| `case_mismatch` | The candidate's actual folder/file/extension casing differs |
| `ambiguous` | Multiple candidates remain; extension priority/selection is not inferred |
| `unverified_extension` | A candidate exists in a format outside this audit's verified search set |
| `unresolved_without_rtp` | No local candidate, and no RTP was supplied |
| `missing` | No candidate in the project or the explicit RTP search root |
| `unsafe_reference` / `opaque_reference` | The name cannot be safely resolved or was not decoded as text |

Each distinct folder/name pair has its total reference count and up to three exact source-file/JSON-path evidence samples. Matches identify project versus RTP and relative paths, without embedding absolute RTP paths. Reports are `asset-audit.json` and `asset-audit.md`. Exit `0` means all discovered references are `found`; `3` means review is needed; `2` is a refusal/error.

The master enables `asset_audit: true`; `--rtp` is passed only to that read-only stage. Older custom configurations that omit this flag continue without the stage; strings such as `"false"` are refused instead of treated as booleans. Asset findings do not change the separate byte-mutation readiness gate.

## Limits and evidence

No image decoding/dimensions, audio playback, licensing, encrypted archives, implicit engine assets, script/note references, dynamic names or runtime-created content are validated. A `found` file can still be corrupt or incompatible. Source/index integrity is rechecked; RTP asset names, sizes and modification times are rechecked, not complete file hashes.

Eighteen asset tests cover fallback uncertainty, local priority, casing, explicit/nested/dotted names, format ambiguity, unsafe/opaque names, provenance, bounded evidence, stale reports, linked files, wrong RTP roots, budgets, metadata changes and RTP text sidecars. Two master configuration tests cover strict flags and older configurations. Windows may skip link-creation tests when privileges are unavailable.

The actual private Oakfall index resolved all 290 distinct indexed asset references against the explicitly supplied installed VX Ace RTP. Real testing exposed tileset `.txt` sidecars as false competitors; the implementation now excludes them and has a regression test. Native playtesting separately observed the village characters, tiles, title and guardian graphics/audio. Runtime-created Oakfall NPC names are outside static reference collection; no broader asset completeness claim follows from that observation. Project/RTP data and private reports remain local.
