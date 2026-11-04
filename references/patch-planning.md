# Reversible project-aware patch planning

The patch planner is a proposal-only layer on top of a fresh Project Reader index and Codex. The guarded copy patcher and the recipe runner apply a plan to a disposable copy (see [recipes](recipes.md)).

## Safety invariant

The planner never modifies the VX Ace source project.

Outputs must be a new unlinked directory outside both source project and index; existing output directories are refused. [Script-slot proposals](script-slot-insertion.md) include the complete new-source diff/hash and native archive/anchor preconditions after verifying the current canonical Main snapshot. Planning still never inserts or executes code.

It may:

- verify that every source file recorded by `manifest.json` still has the same SHA-256 hash;
- refuse a stale index;
- generate exact unified diffs against extracted RGSS3 script text;
- describe event and database changes using structured locators and proposals;
- emit regression and rollback guidance.

The planner itself may **not**:

- rewrite `.rvdata2`;
- inject scripts into `Scripts.rvdata2`;
- modify source project files;
- apply a proposal; applying is a separate, guarded step.

## Freshness rule

A patch plan is valid only against the exact source snapshot that produced its index.

Before generating a plan, pass the current project directory. The planner hashes every file recorded in the index manifest and compares it to the stored hash. Any mismatch or missing file causes a hard refusal with exit code `3`.

This prevents an agent from preparing a patch against outdated maps, scripts, database objects, or assets.

## Script changes

Script changes target the extracted text under `index/scripts/`.

A patch specification supplies:

- `script_path` from the extracted index;
- an exact `search` block;
- a `replace` block;
- optional description/risk metadata.

The search block must occur **exactly once**. Zero or multiple matches are refused because a fuzzy/ambiguous patch is unsafe.

The output includes:

- original extracted-script SHA-256;
- unified diff;
- proposal-only apply mode.

A human or the guarded copy patcher can use that diff while respecting Script Editor load order and compatibility findings.

## Event/database changes

The planner describes event and database changes structurally; the guarded copy patcher writes them.

Examples of event locators:

```json
{"map_id": 4, "event_id": 12, "page": 3}
```

```json
{"common_event_id": 8}
```

Database locator:

```json
{"table": "states", "id": 14}
```

The proposal explains the intended mutation; the planner does not serialize it into VX Ace data.

## Regression generation

The planner adds baseline checks plus domain-specific checks for scripts, events, and database changes. Every plan ends with re-running the Project Reader and comparing the post-change index/codex with the pre-change snapshot.

## Rollback

Because the planner does not apply anything, rollback at planning time is trivial. Writers work on a disposable copy; the project changes only through `vxace_adopt.py` (backup and undo) or a confirmed in-place recipe run (one verified backup). If you apply a proposal by hand, keep a restorable backup and revert if regression testing fails.

## Writer gate

A change reaches the project only after all of these hold; the copy patcher, adopt and the in-place recipe run enforce them:

1. parse -> serialize round-trip fidelity on copies;
2. unchanged-project byte or semantic equivalence where expected;
3. source freshness checks at apply time;
4. explicit human-readable diff;
5. backup/restore path;
6. post-write re-index and codex diff;
7. runtime regression testing.
