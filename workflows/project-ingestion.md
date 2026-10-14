# Workflow — Project Ingestion (v0.5)

## Objective

Produce a read-only project index from a legally accessible RPG Maker VX Ace project and use it as the source of truth for project-specific reasoning.

## 1. Preserve the source

Before analysis:

- do not edit `Data/*.rvdata2`;
- do not edit `Scripts.rvdata2`;
- do not put generated output inside the source project;
- do not execute extracted scripts;
- keep the original project backed up independently when later editing is introduced.

## 2. Run the reader

```bash
python tools/vxace_project_reader.py PATH_TO_PROJECT
```

Use `--output` for a specific external destination and `--ruby` if Ruby is not on `PATH`.

## 3. Inspect `project.json`

Check:

- decoded database files;
- map count;
- extracted script count;
- compatibility-analysis status;
- extraction errors.

A partial extraction must not be treated as complete project knowledge.

## 4. Use symbolic project indexes

For project questions, prefer generated sources in this order:

1. `analysis/event-references.json` for cross-event relationships;
2. dedicated switch/variable/common-event/transfer/battle indexes;
3. `analysis/script-compatibility.json` for script overlap;
4. normalized `maps/*.json` for page/command inspection;
5. normalized `database/*.json` for database details;
6. extracted scripts in actual `scripts/order.json` order.

## 5. Verify before changing

A reader finding is evidence, not permission to patch automatically.

Before implementation:

- trace the exact map/event/page or common event;
- inspect relevant RGSS3 definitions in real load order;
- verify all IDs/names from the index;
- identify save compatibility;
- produce a concrete regression test.

## 6. Refresh after project changes

The project index is a snapshot. If the project changes, regenerate it rather than assuming hashes, event paths, or script order remain valid.

## 7. Publication boundary

Do not upload extracted project scripts, normalized project data, or third-party scripts to a public repository unless the user explicitly requests publication and has the right to publish that material.
