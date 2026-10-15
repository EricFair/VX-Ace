# Gradual upstream adoption — first batch

Initial batch: local development on top of v0.10. Updated in v0.11: the pinned codec now also powers an explicitly selected, narrowly scoped production data backend after synthetic and real-project comparison. See `real-project-validation-v0.11.md` for the exact evidence and limits.

## Source and intent

Reference: [azureknight63/rpgvxace-mcp](https://github.com/azureknight63/rpgvxace-mcp), pinned to `75d7360fc12eda3046881e0424f136a9a5c01487`. A complete detached reference clone and tracked-file hash manifest are retained outside this repository in the workspace's `reference-vault/`. That archive remains independent from our toolchain.

Adopt useful capabilities incrementally under **our** rules: VX Ace first, fresh evidence, no original mutation, exact byte gates, proposal review, disposable copies, re-indexing, semantic diff, and actual RGSS3 runtime tests. Upstream readme/test claims are not evidence collected against the user's project.

## Capability inventory and sequence

| Capability missing or narrower here | Adoption decision | Acceptance evidence |
| --- | --- | --- |
| Python-native Marshal codec and opaque values | Batch 1: isolated read-only codec audit, implemented | Pinned conformance suite; refusal and immutability tests; then cross-backend and real-project comparisons |
| Observed per-project schema, unknown-field reporting | v0.11: observed class/field/type report; unknown-field classification remains future work | Compare observations against fresh normalized data; preserve evidence paths and unknowns |
| Broken-reference and transfer-coordinate linting | v0.11: direct transfer, common-event and troop reference checks | Known-valid/invalid project fixtures; variable-designated transfers distinguished from direct transfers |
| RTP-aware graphics/audio validation, case mismatches | v0.15: read-only presence/casing; v0.17: optional PNG header/layout observations | Explicit external RTP; absent RTP remains uncertain; bounded header checks and native frame comparisons; full decoding/dynamic assets deferred |
| Event-page shadowing, autorun and label linting | v0.13: conservative read-only batch | Complete flags, highest unconditional map page, local labels and continuations; native cutscene/shadow fixtures, opaque behavior disclosed |
| Cross-project text/command search | v0.13: external-index literal search | Exact evidence per hit; bounded input/walk/output, full selected-scope counts and pagination; regex deferred; never evaluate scripts |
| MCP tools/resources interface | v0.18: optional read-only stdio adapter over our APIs | Five bounded tools/fixed summary URI; fresh source/index checks, strict protocol/deadline tests and private native-project client; writes remain separate planner/copy-patcher operations |
| Database entry creation/deletion | v0.20: narrow inert key-item append; other creation/deletion deferred | Exact native array/template hashes and schemas, next static ID, unchanged existing entries, dynamic-consumer review, clone/postgates and native inventory/save evidence |
| Event/page/command structural authoring and DSL | Partial in v0.12 | Guarded native command units and conditioned template pages implemented in our Python copy chain; broad DSL/branch/script authoring deferred. See `event-structure.md` and native evidence |
| Map create/delete/resize and map-tree updates | Deferred | Multi-file clone transaction; tile preservation and reference linting; runtime checks |
| Tile read/paint/fill and region-layer operations | v0.14: read-only tile/region diagnostics; v0.19: guarded existing region cells; graphic painting deferred | Exact native Table/current-region preconditions, editor IDs0..63, approved-byte preservation, impact, version reload and clone/native save tests; no graphic tile writer |
| Script-slot creation/reordering | Deferred | Script order/dependencies/save hooks; unambiguous targets; compatibility and runtime tests |
| Codec encoding preservation and code-page reporting | Codec bytes retained now; presentation later | UTF-8/CP932/CP1252 fixtures; explicit uncertainty; no guessed lossy conversion |
| Per-file stale checks, backups, dry runs, logs | Retain our freshness/plans/audit/clone controls; adapt useful diagnostics | Do not replace source immutability with in-place backups or confuse per-file atomicity with whole-patch transactions |
| Raw arbitrary field writes | Do not expose in production | Our verified-field and schema restrictions remain authoritative |
| VX support | Reference only for now | Separate explicitly requested scope; never silently broaden our Ace behavior |

## Batch 1: experimental read-only audit

```text
python tools/vxace_codec_audit.py "<VX_ACE_PROJECT>" --output "<NEW_EXTERNAL_REPORT_DIR>"
```

Python 3.10+; no Ruby needed for **this audit only**. Existing reader, validator and patcher requirements remain unchanged.

The audit compares each immediate `Data/*.rvdata2` file to an in-memory no-op decode/encode result. Each file runs in a separate subprocess with a timeout (default 30 seconds; `--timeout` changes it). Files over 64 MiB and linked data paths are refused. Warnings, mismatches, codec errors and timeouts are failures. Before/after Data hash inventories must match. Hash comparisons detect differences; they are not a filesystem lock or an OS security sandbox.

Reports are `codec-audit.json` and `codec-audit.md` in a new directory outside the source. Existing output directories are refused. No round-trip candidate, normalized source data or extracted script is written. The audit neither executes scripts nor edits game files.

Exit `0` means the experimental codec audit passed, `3` means refused, and `2` means configuration/execution error. A pass deliberately reports `mutation_authorized=false` and `production_gate_satisfied=false`. It does not emit `copy_mutation_ready`. Our production `vxace_project_validator.py` and immediate Ruby-mutator gates remain mandatory and unchanged.

Only `marshal_rb.py`, `rubytypes.py`, package metadata, and their pinned codec tests are adopted. The upstream MCP server and game writer are not imported. See `tools/_vendor/NOTICE.md` and hash manifest.

## Verification and promotion gates

1. Run `python -m unittest discover -s tests/marshal_codec -p "test_*.py" -v` and the complete `python tools/run_tests.py` suite. The full runner includes the new suite, so existing GitHub Actions also exercises it.
2. Compare both backends on our Ruby-generated VX Ace fixture; confirm decoded identity/reference and native payload behavior, not only self-generated Python fixtures.
3. Run both audits against actual user-owned projects, keeping originals unchanged and all reports external. Do not declare real fidelity based only on upstream's reported project.
4. Investigate every disagreement with a minimal reproducible fixture. No gate downgrades.
5. Only after evidence and review consider an optional Python reader backend. Mutation remains with the current gated implementation until separately proven.

Batch 1 stopped before production selection. v0.11 adds explicit Python backend selection, the master workflow and observed-schema/reference inspection. Individual tools retain their Ruby default; no silent fallback or structural editing is added. The standalone experimental audit still never grants readiness. Further batches should remain small, tested changes rather than wholesale imports of upstream behavior.
