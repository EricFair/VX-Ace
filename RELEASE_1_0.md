# v1.0 release contract

Scope frozen by user direction on 15 October 2026. The goal is to ship a useful, verified VX Ace specialist, then iterate after release. Full upstream feature parity is not a v1.0 requirement.

## Fixed scope

Release the existing validated analysis, planning, copy-only editing and playable-slice workflows, plus the currently pending bounded one-time event reward feature. Preserve all source immutability, freshness, byte preservation, privacy, native testing and rollback requirements. Unsupported operations must remain documented and refused.

Do not start another feature batch before v1.0. Do not require another project, complete upstream parity or universal compatibility to release. Existing real-project and native evidence must be reviewed honestly; supported-project limitations belong in the release notes.

## Finite release checklist

1. Finish the saved reward verification: repair the private native test driver through fresh disposable copies; verify first grant, repeat prevention, inventory, old-save loading, saving and process restart. Confirm the complete test-suite result. Fix demonstrated defects within this scope.
2. Perform one release-candidate review of the supported workflow: run required automated checks and the read-only master workflow, review existing native playable-slice evidence, and rerun native cases affected by subsequent changes. Verify original/source preservation and public-file privacy. A concrete correctness, safety or supported-workflow failure blocks release; optional enhancements do not.
3. Finish user-facing setup, supported operations, known limitations, evidence summary and changelog; make version metadata consistent at 1.0.0. Verify a clean install and documented entry points. Documentation must not claim unperformed checks or general compatibility from limited fixtures.
4. Publish the verified v1.0 repository state and release, confirm CI on that exact commit, install that exact version and check installation hashes. Report the release link and supported usage. This completes the v1.0 milestone.

If a check fails, repair the specific failure and rerun affected checks. Do not restart feature discovery or expand acceptance criteria. If the reward feature cannot safely pass, report the specific blocker and propose an explicit deferral rather than silently extending the milestone or weakening a gate.

## After v1.0

The broader backlog moves to later releases: map creation/deletion/resizing; ground/autotile/fill editing; broader database creation/deletion; advanced event authoring; script reordering/deletion; writable MCP; full image/dynamic asset validation; deeper control-flow analysis; regex search; unknown-field classification; broader encoding presentation. Prioritize these after v1.0, with separate acceptance evidence. They are not promised collectively for v2.0.

VX/RGSS2 support and unrestricted raw writes remain outside scope. Release numbering must never imply unrestricted writes or compatibility that has not been verified.

After publishing v1.0, close the v1.0 checklist and update continuation state explicitly before starting a separately scoped post-release milestone. Preserve the user's usage/reset limits throughout; never consume the manual reset credit.
