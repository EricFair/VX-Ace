# Guarded native key-item append — v0.20

Use this narrow operation to add one inert quest key item to an existing native Items database. It does not create other database objects, reuse holes/IDs, delete/reorder entries, author usable effects or edit saves.

## Exact preconditions and spec

Build a fresh external Project Reader index, then capture native array/template preconditions:

```powershell
python tools/vxace_database_entries.py PROJECT_INDEX --project PROJECT --template-item 1 --output NEW_EXTERNAL_SNAPSHOT
```

The read-only snapshot requires byte-identical native decoding, matching indexed/native item identities and a supported template schema. It returns the complete Items array and isolated template Marshal SHA-256 values, plus the next append ID. IDs already used by static entries cannot be reused. The supported limit is new IDs 1..999; a full supported array reports `append_slot_supported: false`. A snapshot is not mutation permission.

Use actual captured hashes and the exact next ID in a reviewed spec:

```json
{
  "title": "Add a reviewed quest key item",
  "changes": [{
    "kind": "database_entry",
    "locator": {"table": "items"},
    "proposal": "Append one inert key item after reviewing dynamic IDs and inventory consumers.",
    "mutation": {
      "action": "append_key_item",
      "template_id": 1,
      "new_id": 17,
      "expected_array_sha256": "REPLACE_WITH_EXACT_ARRAY_SHA256",
      "expected_template_sha256": "REPLACE_WITH_EXACT_TEMPLATE_SHA256",
      "name": "Village Relic",
      "description": "A keepsake to return to the village elder."
    }
  }]
}
```

The array must have nil slot zero and every existing entry must be a native `RPG::Item` with its exact array-slot ID. No sparse arrays, aliases under duplicate IDs or foreign database classes are admitted. The selected template must have exactly the supported 19 native Item fields, matching native types, empty item features, recognized finite native effects and a native no-damage object with the exact supported schema. Unknown/missing selected fields or custom damage/effect classes refuse creation. Other existing entries are retained unchanged, including their existing extra fields.

The template is deeply cloned, then the new record is forced to inert native settings: Key Item, no scope, Never usable, nonconsumable, zero price/icon, no features/effects/note tags, neutral invocation settings and zero damage/formula. Only the bounded name and description are supplied by the spec. Name length is 1..100 without controls; description is at most 1000 characters and may contain newlines. Existing string encoding rules remain enforced; no guessed lossy legacy conversion occurs. Icon 0 is deliberately the narrow initial default; a later scalar edit needs separate asset/native review.

Candidate verification requires the entire original array prefix to serialize identically and the one appended record to match the approved factory result exactly. It does not merely count entries or trust a self-generated round trip. Other Items mutations in the same transaction, multiple appends and arbitrary new fields are refused.

## Impact and disposable staging

```powershell
python tools/vxace_patch_planner.py PROJECT_INDEX --project PROJECT --spec key-item-patch.json --output NEW_PLAN
python tools/vxace_impact.py PROJECT_INDEX --spec key-item-patch.json --json NEW_IMPACT.json --markdown NEW_IMPACT.md
python tools/vxace_copy_patcher.py PROJECT_INDEX --project PROJECT --spec key-item-patch.json --copy NEW_COPY --audit NEW_AUDIT --backend python
```

The explicit Python backend, fresh source/index, complete project/target byte gates, new copy/audit paths, mandatory re-index/semantic diff and complete post-copy validation are required. Failed apply/extraction/post-checks remove the whole partial copy and retain the failure audit. Existing Items entries are verified unchanged. Appending only a database entry does not advance `System.version_id`; the database reloads on normal startup. If the transaction separately changes guarded map regions/event structure, their normal single version advance still applies. This is not general save migration.

The high-risk impact report verifies indexed IDs/template identity and lists bounded literal item/inventory mentions in ordered scripts and event content. Exact native hashes/schema are checked separately by the snapshot/copy backend. Review runtime-created IDs, inventory extensions, note consumers and custom save behavior. A statically unused append ID may already be created dynamically; absence of literal mentions does not prove compatibility.

In particular, the public Oakfall example intentionally creates runtime item17 and asserts that slot is free. Do not append static item17 to that project and leave its helper unchanged. This tool's acceptance tests use a separate blank seed copy; they do not silently migrate the known-good playable example.

## Native verification

Inspect the new entry in the editor, confirm an existing template item still has its original behavior, and test actual native inventory categorization/counts and engine save/full-process-restart loading on a disposable copy. Keep all runtime harnesses, saves and raw project evidence private. The normal master/MCP interface remains read-only and never appends entries automatically.

Thirteen new public tests cover native schema/types, exact hashes/IDs, inert defaults, deep independence, unchanged existing records, candidate tampering, text/encoding limits, array capacity, external/stale snapshots, explicit backend/postgates and complete rollback. The independent Ruby fixture defines original native-shaped objects; proprietary engine scripts or databases are not distributed.

The complete 307-test runner passed locally. In a private disposable blank-seed copy, the native editor displayed appended item 017 as Key Item, Never usable, nonconsumable, no scope/damage/effects/note and zero price; the original Potion retained its healing effect. Native `Game_Party.gain_item` and `Window_ItemList`'s Key Item category showed exactly one new item. A private harness called actual engine saving once, then normal Continue/File1 after a full Game-process restart restored the same item/count/filter and unchanged save bytes. All existing Items entries and System data matched the source. This is native engine inventory/persistence evidence, not a claim that arbitrary custom inventory extensions or UI-menu Save were tested.
