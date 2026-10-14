# Workflow — Impact Review and Semantic Verification

## Before staging a patch

1. Run `vxace_project_validator.py` when establishing project mutation readiness.
2. Generate a fresh Project Reader/Codex index.
3. Prepare the reviewed patch spec.
4. Run:

```bash
python tools/vxace_impact.py PROJECT_INDEX --spec patch.json --json impact.json --markdown impact.md
```

5. Review every reported relationship, collision candidate, save hook, and limitation.
6. If the report exposes an unexpected high-risk script collision or wrong target, stop and revise the plan.
7. Only then use proposal planning or copy mutation if the change fits the currently allowed writer.

## After a staged copy is re-indexed

Run:

```bash
python tools/vxace_semantic_diff.py BEFORE_INDEX AFTER_INDEX \
  --json semantic-diff.json --markdown semantic-diff.md
```

Review added/removed/changed Codex systems, state machines, graph relationships, and script metadata. Unexpected semantic changes are a stop signal even when the binary mutation itself succeeded.

## Non-negotiable boundary

Neither impact analysis nor a clean semantic diff substitutes for opening the staged copy in RPG Maker VX Ace and performing project-specific runtime tests.
