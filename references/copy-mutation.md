# Verified Copy Mutation — v0.8

Historical foundation: v0.11 adds an explicit Python backend and v0.12 adds [guarded command/page structure edits](event-structure.md) through that backend. The v0.8 limitations below describe that original release; the linked workflow defines the current structural subset and mandatory gates.

v0.8 introduces the first mutation-capable layer, but it is intentionally restricted to **disposable project copies**.

## Safety contract

The source VX Ace project is never a write target.

Before any mutation, the copy patcher must:

1. verify the source project against the Project Reader manifest, including changed, missing, and newly added files;
2. identify every `.rvdata2` file that would be touched;
3. perform a no-op load -> Marshal dump round-trip on each target;
4. require both the normalized semantic hash **and the raw SHA-256** to match exactly;
5. refuse the patch if any target fails that round-trip gate;
6. clone the source project to a new destination;
7. mutate only files in the clone;
8. confirm the source file inventory/hashes are unchanged afterward.

This is stricter than merely proving that Ruby can read and rewrite the file. Exact binary identity is the v0.8 admission requirement.

This reference retains the v0.8 baseline contract. Current separately gated additions are [event structure](event-structure.md), [existing-map regions](map-region-editing.md), [inert key-item append](key-item-append.md), [one native slot before canonical Main](script-slot-insertion.md), [ordinary upper B-E tiles](upper-tile-painting.md), and [stationary dialogue-event append](map-event-creation.md) with [optional bound character graphics](character-event-graphics.md). Those references define their narrower native schemas, Python-only selection and mandatory postgates; the historical v0.8 refusal list below does not enable or describe those later operations.

## Supported mutations

### RGSS3 Scripts archive

A script is addressed by the extracted Script Editor path/order from the Project Reader index. The mutator resolves that path back to the archive index, inflates the script, requires the search block to occur exactly once, replaces it, recompresses it, and writes a new `Scripts.rvdata2` in the staged copy.

### Database objects

A limited database mutation can set one **existing** instance-variable field on a verified object ID in a supported database table. Values are restricted to JSON-representable structures by the copy patcher contract.

This is suitable for tightly scoped fields such as a name or numeric property. It is **not** permission to perform broad arbitrary schema edits or create new object fields.

### Event command parameters

v0.8 can modify parameters on an existing event command in:

- a map event page;
- a common event;
- a troop event page.

It does not yet insert/delete event commands or pages. Existing structure must already exist and be addressable by verified IDs/page/command indexes.

## Transactional failure behavior

The copy patcher is fail-closed. If mutation, verification, or re-indexing fails after the staged copy is created, the staged copy is deleted automatically. The audit directory remains and records `failure.json` so a partial copy is not mistaken for a usable build.

## What v0.8 still refuses

- direct mutation of the original project;
- any target that cannot round-trip byte-identically first;
- stale Project Reader indexes;
- output or audit paths inside the source project;
- nested copy/audit destinations;
- ambiguous script replacements;
- arbitrary Ruby execution from project scripts;
- structural insertion/deletion of events/pages/commands;
- creation of unknown database instance variables;
- unverified writers for unknown/custom serialized classes;
- save-file migration or modification;
- encrypted game archives.

## Verification outputs

The copy patcher produces an audit containing:

- source freshness result;
- per-target round-trip proof;
- before/after raw SHA-256;
- before/after normalized semantic SHA-256;
- script unified diffs where applicable;
- proof that source hashes remained unchanged;
- optional post-copy Project Reader index;
- optional normalized index diff.

The staged project should still be opened and tested in RPG Maker VX Ace before any human decides to replace a working project with it.

## Why byte-identical no-op round trips matter

Ruby Marshal is a serialization format, not a schema-aware database. A writer can produce a file that appears semantically similar to an external parser while still differing in details important to the real runtime. Requiring an exact no-op byte match greatly reduces that risk.

It is not a complete proof of game correctness. It is a precondition for v0.8 mutation.
