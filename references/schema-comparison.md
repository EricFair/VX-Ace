# Baseline-relative observed schema comparison — v1.3

Use this standalone read-only report to find classes, fields and normalized type sets that differ from an explicitly selected baseline project. It complements the existing single-index observed schema report. It does not supply a universal VX Ace schema, classify new fields as invalid, or authorize writing them.

Generate a fresh Project Reader index for each actual project, then run:

```powershell
python tools/vxace_schema_diff.py BASELINE_EXTERNAL_INDEX TARGET_EXTERNAL_INDEX --baseline-project BASELINE_PROJECT --project TARGET_PROJECT --output NEW_EXTERNAL_REPORT
```

Both project arguments accept a project folder or its `.rvproj2` file. Both manifests must be complete, hashed, read-only and fresh against all current source files. Output must be new and outside both projects and indexes. Linked paths are refused. Both source inventories and every read index file/selected file set are checked again before reports are written. Files are not locked; close editors/playtests while collecting stable evidence.

`schema-diff.json` records:

- classes `only_in_target`, `only_in_baseline` or `shared`, with object counts and up to three exact index-relative sample paths per side;
- each field's status, observation count, normalized type counts and up to three sample paths per type/side;
- shared-class fields observed only on one side, or with a changed type set;
- separate baseline/target manifest and complete project-inventory hashes, plus read-only/freshness/integrity flags.

`schema-diff.md` gives counts and limits. A class observed on only one side is counted once as a class difference; its fields remain listed but are not counted again as shared-class field drift. Differences in object counts alone do not imply a schema change. JSON primitive/container types include `NoneType`, `bool`, `int`, `float`, `str`, `list` and `dict`; these are normalized observations, not full Ruby Marshal types or runtime semantics. Reader metadata keys beginning `__` are excluded from field classification.

Choose a baseline with relevant content coverage. A field/class absent from one project may simply have no corresponding object there. The report is descriptive, not an automatic compatibility verdict. Scripts, opaque extraction, dynamically created fields/classes and save state are outside its coverage. Never run inspected scripts to fill those gaps or add an unknown field because this report lists it.

## Fixed bounds

Each index retains the shared 16MiB/file, 128MiB total read, 4,096 read and 500,000 charged-step budgets. Traversal depth is at most128 and evidence/class keys at most256 characters. Each side allows at most2,048 classes, 50,000 distinct class-field pairs and512KiB serialized evidence samples. Each source integrity inventory allows20,000 filesystem entries,64MiB/file and512MiB total bytes. The JSON report is capped at2MiB. Exceeding any budget refuses the whole comparison without a partial report; source integrity reads use bounded chunks. These are fixed safety/resource limits, not pagination.

## Evidence and limits

Eleven focused tests cover baseline-relative classes/fields/types and exact evidence, nested classes, primitive/container types, sample caps, count-only differences, both stale/incomplete inputs, both source/index changes, containment/link refusal, resource limits and report-write cleanup without input changes. Platform-dependent symlink creation can be skipped where unavailable; CI reports the actual result.

A private fresh comparison of the editor-produced seed and v1.2's native-tested map copy reported no class/field/type-set differences while recording increased map/map-info counts. An independent authored Ruby Marshal fixture with one added `RPG::Actor.custom_schema_flag` reported exactly one target-only field with a boolean observation and exact normalized evidence. Neither comparison executed project scripts or modified either source. Proprietary project/index/report content remains private. Check the release commit's actual full-suite and CI results before claiming it passed online.

This standalone tool does not change master policy, mutation gates, existing inspection results, literal/regex search or MCP. Further schema classification or authoring needs separate evidence and scope.
