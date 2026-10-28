# Getting started

This is an RPG Maker VX Ace specialist skill plus a local toolchain. It helps design mechanics, analyse a project, stage guarded additions on disposable copies, test them in the real engine and adopt reviewed results into your project. You need a legally installed RPG Maker VX Ace; the skill ships no engine scripts or assets.

## Requirements

- Windows with RPG Maker VX Ace (the smoke tests launch the project's real `Game.exe`).
- Python 3.10+ and Ruby 3.2 on PATH. Ruby is only used for extraction and host diagnostics; the game itself still runs RGSS3/Ruby 1.9.2. No pip installs are needed.

## Install

**Claude Code** (skills are discovered from `~/.claude/skills`):

```powershell
git clone --branch v1.18.0 https://github.com/EricFair/VX-Ace.git "$env:USERPROFILE/.claude/skills/rpg-maker-vx-ace-developer"
```

**Codex**:

```powershell
git clone --branch v1.18.0 https://github.com/EricFair/VX-Ace.git "$env:USERPROFILE/.codex/skills/rpg-maker-vx-ace-developer"
```

Start a new chat so the skill is discovered, then name your project folder, for example *"Use the VX Ace skill on C:/Games/MyGame"*. To update later: `git fetch --tags` and `git checkout` the newer tag inside that folder. Keep `SKILL.md`, `tools`, `references`, `workflows`, `patterns` and `templates` together.

## First session: read only

Save and close the editor first. Ask for a read-only first pass:

> Do not modify my project. Validate it, index it and summarise its systems, scripts, balance and any problems. Do not stage anything yet.

Behind the scenes this runs, with new report folders outside the project:

```powershell
python tools/vxace_project_validator.py "C:/Games/MyGame" --backend python --output "C:/VXReports/MyGame-validation"
python tools/vxace_master.py "C:/Games/MyGame" --output "C:/VXReports/MyGame-master"
```

A failed byte-identical check blocks all staging for that project until it is investigated. Keep reports private: they can contain your scripts and data.

## Making changes

Describe what you want; the agent picks native features first and stages the change on a **copy**, never on your project:

- single additions — enemies, skills, states, weapons, armors, troops, class learnings, encounters, shops, dialogue NPCs, transfers, rewards ([database append](references/database-append.md), [map shops](references/map-shops.md), [encounters](references/map-encounters.md));
- several at once — a [recipe](references/recipes.md), for example `tools/recipes/example_cave.json` (enemy → skill → troop → encounter) or `example_smith.json` (weapon → NPC → shop);
- text — [export](references/text-export.md) to CSV, edit in Excel, [import](references/text-import.md).

Each staged copy is smoke-tested in the real engine ([smoke testing](references/smoke-testing.md)); you can also open it in the editor and play it. When you are satisfied, the agent prepares an [adopt plan](references/adopt.md); after you confirm, the reviewed files are copied into your project with a backup and an undo record.

The full loop is described in [daily game development](workflows/daily-game-dev.md). Drawing maps and fine-tuning in the editor stay manual on purpose.

## Where to look next

- [SKILL.md](SKILL.md) — the agent's rules and task routing.
- [VXACE_MASTER.md](VXACE_MASTER.md) — capability matrix and settings.
- [Release checklist](workflows/release-checklist.md) — before shipping a build.
- [Oakfall example](examples/oakfall/README.md) — a small playable original quest slice.
