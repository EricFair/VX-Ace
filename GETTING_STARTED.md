# Getting started with v1.4

This is a VX Ace specialist skill and local toolchain. It helps design mechanics, understand a project and stage supported edits on new copies. It requires a legally installed RPG Maker VX Ace for native editor/playtesting. It does not redistribute engine resources or promise automatic creation of every part of a game.

## Requirements and installation

Use Python 3.10+ and Ruby 3.2 on PATH. CI uses Python 3.11 and Ruby 3.2. Ruby is for extraction and separate host diagnostics; the game still targets VX Ace's RGSS3/Ruby 1.9.2 runtime. The Python codec is vendored with provenance; the normal tools require no pip installation. The optional read-only MCP adapter is not required.

Clone the release into a new skill directory in PowerShell:

```powershell
git clone --branch v1.13.0 https://github.com/EricFair/VX-Ace.git "$env:USERPROFILE/.codex/skills/rpg-maker-vx-ace-developer"
Set-Location "$env:USERPROFILE/.codex/skills/rpg-maker-vx-ace-developer"
python --version
ruby --version
python tools/vxace_master.py --help
```

For an existing installation, update it to the release only after preserving any local changes. Start a new Codex chat if needed to discover the installed skill. Ask Codex to use `$rpg-maker-vx-ace-developer` and give the actual project path. The repository root contains `SKILL.md`; keep its `tools`, `references`, workflows and configuration together.

## First pass: read only

Close the game's editor/playtest for a stable snapshot. Replace the paths below with the actual project and **new** report directories outside it. Never place reports in the source, synced references or RTP directory.

```powershell
python tools/vxace_project_validator.py "C:/Games/MyGame" --backend python --output "C:/VXReports/MyGame-first-validation"
python tools/vxace_master.py "C:/Games/MyGame" --output "C:/VXReports/MyGame-first-master"
```

If Ruby is not on PATH, both commands accept `--ruby "C:/Ruby32-x64/bin/ruby.exe"`; use the actual installed path. The master accepts `--rtp "C:/Actual/Unpacked/RTP"` for explicit read-only resource lookup. Without explicit RTP, unresolved resources remain uncertain.

Tell Codex: **Do not modify my original project. Run read-only validation first, report every file's byte-identical result, readiness, syntax diagnostics and unsupported data. Do not patch anything on this first pass.** Host syntax results do not establish native compatibility. A failed byte gate blocks mutation for that snapshot/backend. Keep reports private because they may contain proprietary game/script content.

## First supported change

After read-only review, request one concrete feature. Codex must inspect a fresh index, produce an exact guarded specification and impact review, then use the copy workflow. For an already reviewed private spec:

```powershell
python tools/vxace_patch_planner.py "C:/VXReports/MyGame-first-master/index" --project "C:/Games/MyGame" --spec "C:/VXReports/reviewed-patch.json" --output "C:/VXReports/MyGame-plan"
python tools/vxace_copy_patcher.py "C:/VXReports/MyGame-first-master/index" --project "C:/Games/MyGame" --spec "C:/VXReports/reviewed-patch.json" --copy "C:/VXTests/MyGame-feature" --audit "C:/VXReports/MyGame-feature-audit" --backend python
```

All output paths must be new. The Python backend enables the documented guarded subset; it does not enable arbitrary structural edits. Keep the original closed and untouched. Open **the staged copy's** `Game.rvproj2` in VX Ace, inspect the change and test New Game, relevant older saves, repeat/failure paths, saving and a full process restart. Review the audit, re-index, semantic diff and post-validation. Failed staging removes the invalid copy and retains a failure audit; discarding a tested copy leaves the original intact.

See [the master capability matrix](VXACE_MASTER.md), [release evidence](references/release-1.0-evidence.md) and [the playable fantasy quest example](examples/oakfall/README.md). New NPC dialogue, simple guarded rewards, existing command/page edits and small script extensions are useful starting tasks. v1.2 also supports [one guarded blank-map append](references/blank-map-append.md) from an inert native template. v1.4 supports [one direct transfer from a verified blank event](references/direct-map-transfer.md) to a different inert empty map. Broader map creation/resizing/deletion, ground/autotile painting and broad database/event construction remain later-version work.
