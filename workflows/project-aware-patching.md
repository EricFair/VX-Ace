# Workflow — Project-aware patch plan

## 1. Regenerate the index

Use the Project Reader against the current source project. Do not reuse an old index just because IDs look unchanged.

## 2. Inspect Codex evidence

Use the codex to route investigation, then verify exact normalized source locations and extracted scripts.

## 3. Compatibility preflight

For script changes, inspect `analysis/script-compatibility.json`, actual Script Editor order, and every definition/alias touching the target method.

## 4. Write a patch spec

Choose only verified targets.

- script -> exact extracted script path + unique search/replace blocks;
- event -> map/common-event/troop locator + structural proposal;
- database -> table/id locator + structural proposal.

Do not put guessed IDs into the spec.

## 5. Generate the plan

```bash
python tools/vxace_patch_planner.py INDEX \
  --project PROJECT \
  --spec patch-spec.json \
  --output patch-plan/
```

The planner refuses stale source/index pairs.

## 6. Review output

Review both:

- `plan.json` for machine-readable details;
- `plan.md` for human-readable diffs, proposals, regression checks, and rollback guidance.

## 7. Apply manually or with a future verified writer

v0.7 itself never writes project data.

For RGSS3, apply the reviewed diff in a project copy or via the Script Editor while preserving order/dependencies.

For events/database entries, use the editor manually until structured binary writing has passed round-trip validation.

## 8. Test and re-index

Run the generated regression checklist, then regenerate the project index/codex and compare the result against the original snapshot.
