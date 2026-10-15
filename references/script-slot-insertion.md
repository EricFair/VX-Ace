# One guarded native script slot before Main — v0.24

Use `script_slot` / `insert_before_main` to add one reviewed authored RGSS3 extension through the explicit Python disposable-copy chain. Existing source replacement remains a separate operation. Reordering, deletion, renaming existing entries, arbitrary insertion positions and customized Main anchors are refused.

## Native admission and preservation

The current archive must be an exact byte-round-trippable array with 1..4095 entries, each exactly `[integer_id, native_name_string, compressed_source_string]`. Existing IDs must be unique nonnegative integers within the tool's signed32-bit range; string metadata must be native empty/boolean `E` metadata. Names and decompressed sources must be valid UTF-8. Invalid/truncated/trailing compression, unsupported metadata, extra entry fields and existing duplicate IDs are refused. Existing source bounds remain16MiB each/64MiB total, with4096 entries after insertion. These are conservative tool admission limits, not a statement of every engine limit.

The anchor must be the **unique `Main` entry** with verified native `E=true` name/compressed-string metadata. After removing blank and single-line comment lines, its only source line must be exactly `rgss_main { SceneManager.run }`. Extra startup code, a modified call, duplicate Main labels or unsupported encoding require separate migration/review rather than relaxing this predicate. The Oakfall example's customized Main therefore cannot be used blindly as this insertion anchor.

The mutation supplies exact whole-archive and selected-entry SHA-256 fingerprints, an explicit unused positive signed32-bit ID, a unique1..80-character trimmed name without control codes, and exact nonempty UTF-8 source <=256KiB without NUL. Obtain IDs from the fresh snapshot; never assume an existing game ID or load-order meaning. The source remains caller-supplied data until the staged game is deliberately run.

The new entry uses separate native strings and compressed source. The candidate must preserve the entire old archive's Marshal bytes after removing that one inserted entry, and match the exact approved new entry without aliases to old strings. Every old ID, name, compressed payload, source byte, relative order and existing reference relationship is preserved. Native source is not normalized or recompressed for old entries.

## Obtain a fresh snapshot

Run the usual project validator and reader first. Select the Main index from `scripts/order.json`, then:

```powershell
python tools/vxace_script_slots.py PROJECT_INDEX --project PROJECT --before-index MAIN_INDEX --output NEW_PRIVATE_SNAPSHOT
```

This read-only command rechecks source freshness, complete native/indexed entry metadata and exact indexed source bytes. Its `script-slot-snapshot.json` reports archive/anchor hashes, existing entries, capacity and an unused ID candidate. A snapshot is evidence, never mutation authority.

Construct the concrete spec from that snapshot and reviewed original source:

```python
import json
from pathlib import Path
snapshot = json.loads(Path(snapshot_file).read_text(encoding="utf-8"))
source = Path(authored_source_file).read_bytes().decode("utf-8", "strict")
spec = {"title": "Add reviewed RGSS3 extension", "changes": [{
    "kind": "script_slot", "locator": {"before_index": snapshot["before_index"]},
    "proposal": "Insert the reviewed extension before canonical Main; preserve all existing entries.",
    "mutation": {
        "action": "insert_before_main", "new_id": snapshot["unused_id_candidate"],
        "name": reviewed_unique_name, "source": source,
        "expected_archive_sha256": snapshot["archive_sha256"],
        "expected_anchor_sha256": snapshot["anchor_sha256"]}}]}
Path(spec_file).write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
```

## Review and stage

```powershell
python tools/vxace_patch_planner.py PROJECT_INDEX --project PROJECT --spec PRIVATE_SPEC --output NEW_PLAN
python tools/vxace_impact.py PROJECT_INDEX --spec PRIVATE_SPEC --json PRIVATE_IMPACT_JSON --markdown PRIVATE_IMPACT_MD
python tools/vxace_copy_patcher.py PROJECT_INDEX --project PROJECT --spec PRIVATE_SPEC --copy NEW_DISPOSABLE_COPY --audit NEW_AUDIT --backend python
```

The planner produces the complete proposed source diff/hash and archive/anchor preconditions; it never applies it. Plan outputs must now be new directories outside both project and index; existing directories and linked paths are refused.

Only one slot insertion is allowed per transaction, with **no other `Scripts.rvdata2` mutation** in that transaction. This avoids ambiguous shifted indices and overlapping archive preconditions. The exact supported Python backend, source/index freshness, whole-project byte gate, immediate target gate, candidate preservation, mandatory impact/re-index/semantic diff/post-project validation and complete failed-copy rollback all remain required. `--no-reindex` and Ruby mutation backends are refused. A slot-only insertion leaves System/version data unchanged; a combined supported map/event structural change follows its existing one-time reload-version rule.

Impact reports the new source's static ownership, aliases, save hooks, imports/requires and bounded ordered collision/dependency evidence against the current compatibility index. It always requires high-risk review: attribute-generated methods, dynamic dispatch and metaprogramming can be missed. A clean report never proves compatibility. Re-indexed filenames after the insertion position shift; review those expected path changes against preserved native IDs/source hashes rather than assuming every renamed indexed file changed its code.

## Native acceptance

Before using a staged extension, review its source and dependencies, perform [compile-only native diagnostics](native-syntax-diagnostics.md) on a separate trusted disposable host when needed, inspect the actual Script Editor slot/order/source, and test startup/new game/unchanged older saves/native save/full-process-restart loading as relevant. New persistent fields need explicit old-save defaults; never serialize windows/graphics/sprites or edit save bytes to make a test pass.

Private evidence used a native-created baseline save with no new field, then added one original Game_System extension before Main. All127 entries compiled in a separate trusted native host. The native Script Editor displayed the new slot immediately before Main and retained the exact archive bytes. The extension loaded the unchanged older save with its lazy default0, set7 and saved through native DataManager; a full game-process restart loaded7 without rewriting either save. Native New Game also reached the default map normally. All old script entries/order/bytes, other Data/System files, baseline source and original20 hashes remained unchanged. Projects, source-containing bundles, saves, raw reports and proprietary scripts stay private; public tests use authored fixtures only.
