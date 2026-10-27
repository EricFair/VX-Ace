# RGSS3 templates

Small, original RGSS3 scripts for RPG Maker VX Ace. They are starting points, not drop-in guarantees: adapt names and IDs to the real project, and never invent IDs (configuration values that need a project ID default to `0` = off).

| File | Purpose |
|---|---|
| [notetag_parser.rb](notetag_parser.rb) | Parse `<key: value>` notetags once at database load and cache them on `RPG::BaseItem`/`RPG::Enemy` |
| [hud_window.rb](hud_window.rb) | Map HUD (gold plus one variable) that redraws only on change |
| [menu_command.rb](menu_command.rb) | Main-menu command that runs a common event |
| [save_safe_extension.rb](save_safe_extension.rb) | Add persistent state to `Game_System`/`Game_Party` with lazy defaults for old saves |
| [playtest_debug_logger.rb](playtest_debug_logger.rb) | `$TEST`-only log of switch/variable changes and long-running interpreters |

Each file starts with a header: purpose, install position, compatibility notes, aliases used, save-data impact and configuration constants.

## Install rules

1. Script Editor: insert a new slot **below "Materials" and above "Main"**. One script per slot, named after the file.
2. Order matters when two scripts alias the same method; read the header "Aliases used" and your existing scripts first. Run the project's script compatibility check where available.
3. Set the configuration constants. A `0` ID means disabled; enter real IDs only after creating the matching switch/variable/common event.
4. Prefer a disposable copy of the project for first install.
5. Syntax is limited to Ruby 1.9.2: no `&.`, no required keyword arguments, no `%i[]`, no `.then`, no endless methods, no hash shorthand, no `<<~`.

## Testing

**Test in actual VX Ace.** Host `ruby -c` is diagnostic only: it checks syntax with a modern Ruby and proves nothing about RGSS3 classes or Ruby 1.9.2 behavior.

For any script that stores state also run the checklist in `../../references/data-and-save-lifecycle.md`: new game, save, load, **old save**, map transfer, battle.

## Sources and licensing

These files are original and contain no default or third-party script code. The class and method names they hook (for example `Game_Switches#[]=`, `DataManager.load_database`, `Window_MenuCommand#add_original_commands`) are standard VX Ace names, checked against the default script signatures.

## Native evidence (v1.7)

All five templates were installed above Main in a disposable copy of an editor-created project (with two unrelated custom scripts present) and exercised by a temporary in-engine harness under the actual RGSS3 runtime (`RUBY_VERSION` 1.9.2), in Playtest and in a normal run. Passed: load/compile; notetag parsing, load-time cache and typed accessors; lazy save defaults, migration, a real save/load round trip and loading a save written before the extension existed; the menu command alongside the default commands, its Scene_Menu handler and common-event reservation; HUD creation, refresh on gold change and disposal with Scene_Map; switch/variable logging, the restarting-autorun warning, parallel interpreters ignored; and no logger hooks or log file outside Playtest. This is not a gameplay test of any particular project: re-test after configuring IDs and alongside other scripts that touch the same methods.
