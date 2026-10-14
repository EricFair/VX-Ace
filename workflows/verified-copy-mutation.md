# Workflow — Verified Copy Mutation

Use this only after generating a fresh Project Reader index and reviewing a v0.7 patch plan.

## 1. Re-index the source project

```bash
python tools/vxace_project_reader.py "C:/Games/MyGame"
```

Do not reuse an old index after editing the project.

## 2. Prepare a mutation spec

Example:

```json
{
  "title": "Quest gate fix",
  "changes": [
    {
      "kind": "script",
      "script_path": "012_Quest_System.rb",
      "search": "old unique block",
      "replace": "new block"
    },
    {
      "kind": "database",
      "locator": {"table": "actors", "id": 4},
      "mutation": {"field": "name", "value": "Alicia"}
    },
    {
      "kind": "event",
      "locator": {"map_id": 17, "event_id": 4, "page": 2, "command_index": 8},
      "mutation": {"action": "set_parameter", "parameter_index": 2, "value": 1}
    }
  ]
}
```

Use only IDs and locations verified from the current index/codex.

## 3. Apply to a disposable copy

```bash
python tools/vxace_copy_patcher.py MyGame-project-index \
  --project "C:/Games/MyGame" \
  --spec patch.json \
  --copy "C:/Games/MyGame-v08-test" \
  --audit "C:/Games/MyGame-v08-audit"
```

The tool refuses to proceed if:

- the index is stale;
- the copy/audit destination already exists;
- the copy or audit destination is inside the source project;
- copy and audit destinations are nested;
- any targeted `.rvdata2` file fails exact no-op byte-identical round-trip verification;
- a target object/event/script cannot be uniquely resolved.

If an apply or re-index step fails after staging begins, the staged project copy is removed automatically and `failure.json` is retained in the audit directory.

## 4. Review audit and index diff

Read:

- `audit.json` / `audit.md`;
- `post-index/`;
- `index-diff.json` / `index-diff.md`.

Unexpected changed normalized files are a stop signal.

## 5. Test in VX Ace

Open the **copy**, never the original, and test:

1. project opens without data-load errors;
2. changed scripts compile/run;
3. affected map/event/database behavior works;
4. adjacent event pages/triggers still work;
5. new game works;
6. existing save loads if the change is expected to be save-compatible;
7. transfers/battles/menu transitions around the modified system still work.

## 6. Rollback

Delete the staged copy. The source project was not modified.

Do not automatically promote the staged copy over the original. Human review and backup remain required in v0.8.
