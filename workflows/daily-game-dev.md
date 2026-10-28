# Daily game development with the skill

How a normal working session looks once a game is under way. The agent proposes and stages; you review in the editor and decide what enters the real project.

## Division of labour

| Do in the RPG Maker editor | Ask the agent |
|---|---|
| Draw maps, tiles and autotiles; place scenery | Analyse balance, notetags, text, assets, event logic, script conflicts |
| Fine-tune values while playtesting | Add enemies, skills, states, weapons, armors, troops, class learnings |
| Tweak a single event by hand | Build shops, dialogue NPCs, encounters, transfers, rewards; chain them with a [recipe](../references/recipes.md) |
| Final art and audio choices | Write and review RGSS3 extensions ([templates](../templates/rgss3/README.md)) |
| | Translate or proofread all text ([export](../references/text-export.md) → CSV → [import](../references/text-import.md)) |
| | Smoke-test a change in the real engine ([smoke testing](../references/smoke-testing.md)) |

## One change, start to finish

1. **Save and close the editor.** The tools read the project from disk; unsaved editor changes are invisible to them, and the editor would overwrite adopted files on its next save.
2. **Describe the goal** ("a cave area with two bat enemies, a smith selling an iron sword"). The agent maps it to native features first ([native feature design](native-feature-design.md), [patterns](../patterns/README.md)) and tells you what stays manual (for example drawing the cave map).
3. **Fresh evidence.** The agent runs the validator and reader on the project into an external folder.
4. **Stage on a copy.** One guarded operation, or a recipe of several, writes a new disposable copy; your project is untouched. Review each step's plan and impact report.
5. **Test the copy.** A smoke run boots it in the real `Game.exe` (new game and, if you have one, an older save). Optionally open the copy in the editor and play it.
6. **Adopt.** When you are happy, the agent prepares an [adopt plan](../references/adopt.md) for the copy and shows you the exact files. You confirm; the tool backs up those project files, copies the reviewed ones in, verifies them and keeps an undo record.
7. **Reopen the editor** and carry on. If something is wrong, run the adopt `undo` before making further editor changes.

## Rules of thumb

- One idea per change or recipe keeps reviews and undo simple.
- If you edited the project after staging, re-stage from a fresh index; adopt refuses drifted files instead of merging.
- Keep your own backups too (the editor's project folder copy or version control) — adopt's backup covers only the files it replaces.
- Never adopt a smoke-test copy; it contains the test harness. Adopt the staged copy the smoke test was built from.
