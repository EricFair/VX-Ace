# v0.11 real-project validation evidence

Date: 14 October 2026 (Europe/Budapest). Testing was authorized by the project owner. Only aggregate results and a minimal synthetic float regression are published; original game data, default scripts, local paths and private extracted indexes are excluded.

## Test subject and environment

- One actual project produced by the installed RPG Maker VX Ace editor: 16 `Data/*.rvdata2` files, one map and 126 Script Editor entries.
- Tooling: Windows, Python 3.12.14 and portable host Ruby 3.2.11. The editor/playtest uses the installed VX Ace RGSS3 runtime, not the host Ruby parser.
- Upstream codec revision: `75d7360fc12eda3046881e0424f136a9a5c01487`, retained with hashes and license declarations.

## Read-only baseline and diagnosis

The historical Ruby data backend passed 9 files and refused 7 byte-mismatched files: Armors, Classes, Enemies, Items, Skills, States and Weapons. The refusal was retained. A minimal diagnosis showed modern Ruby emits a different float record (`5e2`) where the editor stored `500`. Similar numeric meaning is not byte identity.

The independent Python codec audit reproduced all 16 files exactly. No project scripts were executed during these checks. All 126 script entries passed the separate host-Ruby syntax diagnostic; this does not establish Ruby 1.9.2/RGSS3 compatibility by itself.

The regression fixture is the standalone Marshal byte string `04 08 66 08 35 30 30`; it contains no private game data. Tests require that original float bytes survive a no-op and an unrelated name mutation.

## Selected production backend and master workflow

With the production validator explicitly selecting the pinned Python backend:

| Check | Result |
| --- | --- |
| All discovered `.rvdata2` files | 16/16 byte-identical |
| Production copy-mutation readiness | true, for this snapshot/backend only |
| Independent Python codec audit | 16/16 pass |
| Host-Ruby Script Editor syntax | 126 checked; zero failures |
| Project Reader / compatibility / Codex | completed |
| Observed classes | 37 |
| Conservative reference inspection | zero findings within its documented coverage |
| Original source inventory | unchanged |

The master workflow finished with `status=pass` and `mutation_performed=false`. It deliberately does not set a runtime-compatibility proof flag.

## Disposable-copy mutation and actual editor/runtime smoke test

A verified existing actor's display name was changed only in a new disposable project clone. The selected-backend project-wide gate passed, then the target file passed immediate semantic and byte-identical preflight. The source manifest was fresh and source integrity remained unchanged. The clone was re-indexed and compared with the source index.

The normalized diff changed the actor database plus Codex inventory/summary metadata. The semantic Codex diff reported zero changed inferred systems, as expected for a display-name edit; this is not a claim that no field changed.

Actual installed application checks:

1. A separate VX Ace editor instance opened the disposable clone.
2. The Actors database displayed the staged test name.
3. Editor Playtest launched the clone's `Game.exe`.
4. The title screen rendered, New Game loaded the map and player, and the in-game menu rendered the changed name (clipped by the stock menu's name column).
5. The disposable game was closed after testing. The original editor/project was not saved or modified by the test.

This smoke test exercised loading and displaying a database edit in the actual RGSS3 runtime. It did **not** test old saves, save migration, all gameplay systems, all event commands, or every possible script/data mutation. No such broad claim is made.

## Automated release verification

The complete local suite passed **136 tests, zero skipped** before final publication checks: the existing 52 tests, 69 codec/audit/provenance tests, and 15 master/Python-backend tests. Both the historical Ruby narrow writer and the Python narrow writer are covered against generated fixtures. CI now runs the same runner on Ubuntu and Windows with Python 3.11/Ruby 3.2; the final GitHub run status should be checked at the published commit.

## Remaining limits

One small editor-produced project plus one name-edit smoke test is limited real-world evidence. Run validation on every new project snapshot and selected backend; never reuse this readiness as blanket approval. Structural commands/pages/maps/database entry creation/deletion remain disabled. The old Ruby backend continues to refuse the legacy-float mismatch; there is no silent fallback or weakened gate.

Private full reports, raw hashes and before/after inventories were retained outside the repository in the local validation workspace. The original full-file inventory was checked after validation, staging and runtime launch with zero differences.
