# v1.0 evidence and supported limits

v1.0 packages the validated VX Ace specialist and its documented copy-only editing subset. It incorporates the previously unpublished v0.28 reward work. It is a stable supported workflow, not full parity with the archived upstream MCP server or universal custom-project compatibility.

## Acceptance evidence

- The 400-test local suite covers extraction/analysis, byte preservation, freshness, refusal, planning, copy transactions, reference/asset/schema diagnostics, supported structural operations, rollback and optional read-only MCP. Platform-dependent link tests can skip when unavailable; check runner output and exact-commit CI rather than assuming all environments behave alike.
- Real editor-produced project files passed byte-identical production validation. Native command/page insertion and deletion, common/troop scenarios and older-save map reload are recorded in [v0.12 evidence](real-project-validation-v0.12.md); diagnostic scenarios are in [v0.13 evidence](real-project-validation-v0.13.md).
- The [Oakfall playable slice](../examples/oakfall/README.md) has native village scenery, lost-item quest, battle victory, defeat/retry, reward, repeat prevention and save/full-restart evidence. It is an original RGSS3 example for a verified default seed; its generated scenery/events appear at runtime and its cottage doors are decorative.
- Later native disposable-copy checks cover regions, inert key-item append, byte-preserving scripts, separate compile-only diagnostics, canonical-Main script-slot insertion, ordinary upper scenery tiles, new dialogue events and normal/single/object character graphics. Operation-specific references document requirements and limits.
- The final reward scenario loaded an unchanged older save, reconstructed the new two-page map exactly once, granted 25 gold and one Potion, selected the self-switch A follow-up, displayed its repeat message without another grant, and showed the actual gold/inventory menus. A native save survived a full Game-process restart with no extra map setup or save rewrite. Items and unrelated Data/source files stayed unchanged. See [reward guards and native evidence](one-time-event-rewards.md).
- All 20 recorded original-project file hashes matched after the final reward check. No proprietary projects, default scripts, RTP, saves, source bundles or raw private reports belong in the release.

These checks use a small default project and specific disposable scenarios. They are not proof for every imported save, third-party script, dynamic asset, custom gain/save hook or arbitrary serialized type. Every new project and concrete change still needs its own evidence and native testing.

## Supported boundaries

Read-only analysis is the default. Mutations require fresh evidence, project-wide and immediate-target byte gates, exact schema/hash/context guards, new copies, impact review, re-indexing, semantic review, mandatory post-validation and rollback. No release setting enables original-project writes.

General map creation/deletion/resizing, ground/autotile/fill editing, broad database construction/deletion, arbitrary branches/scripts through event DSL, script reordering/deletion and writable MCP are deferred. Full asset decoding, regex, deeper control-flow diagnostics, unknown-field classification and broader encoding presentation are also later work. VX/RGSS2, encrypted archives, general save migration and unrestricted raw writes are outside v1.0.

The package/master/core writer version is 1.0.0. Unchanged analysis components retain their historical report-format versions; those values are not the installed package version. Future releases may extend supported operations with separate evidence without reopening the v1.0 milestone.
