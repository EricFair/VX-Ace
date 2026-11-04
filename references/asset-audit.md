# Read-only graphics/audio references

Use this when checking missing assets or filename casing from a fresh project index. It searches the project first, then an optional explicitly supplied unpacked RTP root. It never installs, copies, renames or repairs assets.

```powershell
python tools/vxace_asset_audit.py PROJECT_INDEX --project PROJECT --output NEW_EXTERNAL_REPORT
python tools/vxace_asset_audit.py PROJECT_INDEX --project PROJECT --output NEW_EXTERNAL_REPORT --rtp "C:/Explicit/Path/To/rtp"
python tools/vxace_master.py PROJECT --output NEW_EXTERNAL_REPORT --rtp "C:/Explicit/Path/To/rtp"
```

The RTP root must be a separate directory containing Graphics/ or Audio/. A missing RTP argument leaves unresolved references uncertain; it does not turn a normal RTP-based game into hundreds of proven missing-file errors. Do not guess RTP availability from a registry entry, a successful file name match elsewhere on disk or an installed editor alone. Supply the actual directory when it is known. The standalone command and master require a new external report directory outside the game, index and RTP, with fresh source/index evidence. Report output inside the RTP root is refused before anything is created.

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

By default there is no image decoding/dimension check. `--image-headers` offers for [bounded PNG header and default-layout observations](image-header-layouts.md); the master enables this separate option. These do not decode pixels or validate the full image. Audio playback, licensing, encrypted archives, implicit engine assets, script/note references, dynamic names and runtime-created content remain outside the audit. A `found` file can still be corrupt or incompatible. Source/index integrity is rechecked; RTP asset names, sizes and modification times are rechecked, not complete file hashes.

Real testing exposed tileset `.txt` sidecars as false competitors; they are excluded from image candidates. On an example project every distinct indexed asset reference resolved against the installed VX Ace RTP. Runtime-created names are outside static reference collection, so no broader completeness claim follows.

## RTP auto-detection

`--rtp` is optional. When it is omitted, `vxace_rtp.py` (`find_rtp(project, explicit, autodetect)`) looks for the installed RTP, in this order:

1. an explicit `--rtp` (always wins, never searched);
2. the project's `Game.ini` `RTP=` name (usually `RPGVXAce`) as a registry value under `HKLM\SOFTWARE\WOW6432Node\Enterbrain\RGSS3\RTP`, then under the non-WOW `HKLM\SOFTWARE\Enterbrain\RGSS3\RTP`;
3. the Steam install: `steamapps\common\RPGVXAce\rtp` under every library in `libraryfolders.vdf` (the Steam folder from the registry and the default Steam folders are read first), then `C:\Program Files (x86)\Common Files\Enterbrain\RGSS3\RPGVXAce`.

A candidate must contain `Graphics/` or `Audio/`. The first valid one is used and the **source is reported**: on stderr (`RTP: PATH (source)`), in `asset-audit.md` (`RTP: ...`), in the audit's printed JSON (`rtp`, `rtp_source`) and in the master report (`master-report.json` `rtp.path` / `rtp.source`, and a line in `master-report.md`). A detected RTP inside the project is ignored. With the RTP found, the 297-odd stock files of a normal game resolve (`found`) instead of `unresolved_without_rtp`, so the master stays `pass` when nothing else needs review. If nothing is found the old behaviour stays: unresolved references remain uncertain.

`python tools/vxace_rtp.py PROJECT` prints the result and every place tried (exit 1 when none).

- `--no-rtp-autodetect` (asset audit, master, recipe `plan`/`run`, copy patcher) skips the search; the environment variable `VXACE_NO_RTP_AUTODETECT=1` does the same for every tool.
- Library calls (`audit()`, `workflow()`, `plan_recipe()`, `run_recipe()`) never auto-detect on their own; only the command lines do (`workflow(..., autodetect=True)` is what `vxace_master.py` passes). The master's asset stage is always started with `--no-rtp-autodetect`; the master resolves the RTP itself and hands it over.
- Snapshot tools (`vxace_map_events.py`, `vxace_database_entries.py`, `vxace_upper_tiles.py`) and the read-only MCP server keep their explicit-only `--rtp`; the recipe passes them the resolved path. The smoke tool does not use the RTP.
