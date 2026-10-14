# v0.12 structural validation evidence

Date: 2026-10-14. Environment: Windows, installed Steam RPG Maker VX Ace and its actual RGSS3 playtest runtime; Python 3.12.14 and portable host Ruby 3.2.11. User authorized structural development and testing on disposable copies, then repository publication after passing.

## Original preservation and project scope

The user-owned working project was read only. Its complete 20-file SHA-256 inventory matched the inventory captured at the start of this structural work. The original editor was left open without edits. Native fixture authoring, all tool writes, Battle Test artifacts and save creation occurred in separate private disposable copies outside the original and repository. No proprietary engine scripts, game data, saves, or raw private reports are published.

The tested project has one 17×13 map, 16 production `Data/*.rvdata2` files and 126 Script Editor records. A blank action-button event was created in a disposable seed through the real editor. Existing common event 1 and troop 1 supplied native schemas. This is a small default-runtime project, not evidence for arbitrary custom games.

## Production transaction results

Insertion: five user operations inserted map/common/troop message commands, a common-event call and self-switch operation, then cloned conditioned map and troop pages. Deletion: five user operations removed the inserted map follow-up commands, common/troop commands and both cloned pages while retaining one map/troop page. The patcher adds a sixth internal operation advancing the copied `System.version_id` by one.

Both final copy transactions passed source freshness, complete source/initial clone inventories, 16/16 project byte gates, immediate per-target gates, exact native preconditions, re-indexing, normalized/semantic review and complete 16/16 post-copy validation. Sources remained unchanged. The final insertion was restaged after audit/version safeguards were added; its Map/CommonEvents/Troops files matched the corresponding native-playtested files byte-for-byte. The deletion transaction included the native version increment before its runtime tests.

Private audits retain exact specs, command/page snapshots, readable diffs, dependency impact and before/after hashes. Production copy results are reproducible with the commands and fields in [event-structure.md](event-structure.md); raw reports contain private project content and stay local.

## Actual editor and runtime observations

| Scenario | Observed result |
| --- | --- |
| Inserted map commands | Native editor showed the exact text, common-event call and self-switch command; New Game interaction displayed `BASELINE`, then `COMMAND INSERT`, then `COMMON INSERT` |
| Inserted map page | Native editor showed page 2 with Self Switch A condition and Action Button trigger; the next interaction displayed `PAGE INSERT` |
| Inserted troop commands/page | Native editor showed two pages, cloned page conditioned on Turn 0 with Battle span; Battle Test displayed `TROOP COMMAND INSERT`, then `TROOP PAGE INSERT`, then the normal fight menu |
| Native save creation | Saved from the insertion copy after the self-switch/page transition using the actual game menu |
| Deleted map commands/page | Native editor showed one action page with only `BASELINE`; no inserted follow-up commands or second page |
| Deleted common/troop commands/pages | Native database showed an empty non-triggered common event and one empty troop page; Battle Test proceeded from emergence text directly to the fight menu with no inserted messages |
| Load older save into deletion copy | The saved file was copied byte-identically and loaded through Continue; interaction displayed the remaining `BASELINE` page despite the saved self-switch/page state. Native project-version mismatch reloaded the edited map |

The editor/playtests for disposable copies were closed after verification. Original project files remained unchanged. These are direct native UI observations, not a substitute based on serialization checks.

## Automated evidence and limits

The full executable runner covers 159 tests, including 23 structural/transaction tests. New coverage checks insertion/deletion reversibility across all three scopes, independent map/troop clones, opaque field preservation, native command schemas, compound units and balanced nesting, final terminator/page protection, stale hashes, malformed/ambiguous locators, labels, new references, repeating triggers, version preconditions/overflow, mandatory re-index, post-validation/semantic output and complete rollback after a later failed mutation. CI runs the same suite on Ubuntu and Windows; inspect the current release commit's Actions result for online status. Skill frontmatter validation also passes.

New Text/common/self-switch behavior and map/troop page selection were exercised in the actual runtime. Other admitted command schemas have automated coverage; every future concrete patch still requires native scenario review. Creating branches/scripts, broad DSL authoring, repeating-trigger structure edits, arbitrary schemas, general save migration and custom runtime compatibility remain outside this release. Existing source block structures may be refused conservatively. Old-save map reload can reset transient map event state; custom save hooks need their own tests.
