# Workflow — Real-Project Validation

Use this before the first mutation-capable operation on a real VX Ace project, and repeat after changing the mutator/bridge implementation.

1. Keep the working project untouched and backed up normally.
2. Run `python tools/vxace_project_validator.py PROJECT --output VALIDATION_DIR`.
3. Review every `.rvdata2` row in `validation.md`.
4. If any file is not byte-identical after no-op round trip, classify the project as **mutation-refused** for the current tool version. Do not bypass the failure for “unrelated” files when claiming project-wide readiness.
5. Review Script Editor syntax diagnostics separately. A host-Ruby parse failure needs investigation, but does not by itself mean the binary round-trip gate failed.
6. Generate a fresh Project Reader index after validation and before project-specific planning.
7. Produce/review the patch plan.
8. Use `vxace_copy_patcher.py` only on a new disposable clone; its per-target round-trip gates remain mandatory even after project-level validation.
9. Re-index/diff the staged clone and test it in the actual VX Ace editor/runtime.
10. Record any real-project validation failure as a fixture/repro case when licensing/privacy allow, without publishing the user's project data.

Never convert a validator failure into a warning-only state just to permit mutation.
