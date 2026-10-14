# Integration batch 1 — local validation evidence

Date: 14 October 2026 (Europe/Budapest).

Base: our v0.10 commit `ff79ff98b1c78e6b38050d73298fd4f9308fdeca`. Upstream codec pin: `75d7360fc12eda3046881e0424f136a9a5c01487`.

## Result

Complete local `tools/run_tests.py` run: **121 tests passed, zero skipped** on Windows, using bundled Python 3.12.14 and portable Ruby 3.2.11 x64. No user game was supplied or modified.

| Suite | Tests | Result |
| --- | ---: | --- |
| tooling | 12 | PASS |
| project_reader | 6 | PASS |
| codex | 8 | PASS |
| patch_planner | 5 | PASS |
| mutation | 7 | PASS |
| project_validator | 7 | PASS |
| impact | 7 | PASS |
| marshal_codec | 69 | PASS |
| Total | 121 | PASS |

The 69 codec tests consist of 56 pinned upstream conformance tests, 12 audit/integration safety tests, and one dependency-provenance test. The cross-backend integration test generates our existing fixture with Ruby, runs the production Ruby validator and experimental Python audit separately, requires both to pass, and verifies matching source-file/hash inventories. This is synthetic evidence, not a real-project result or proof that arbitrary edits are correct.

## Environment issues resolved

- Windows' default sandbox temporary directory could not support the test files; test-process `TEMP`/`TMP` were pointed at ignored workspace scratch.
- Ruby was initially absent. A portable RubyInstaller archive was downloaded into the parent workspace, verified against the GitHub release asset's SHA-256, and extracted without a system installation.
- Test-process `RUBYOPT=--disable-gems` avoids RubyGems system-configuration initialization; these tools only need standard libraries.
- Existing mutation tests invoked `python3` by name, resolving to an unusable Windows app alias. Their subprocess helper now uses `sys.executable`, matching the running interpreter. No production mutation behavior was changed.

Final detailed runner log is retained locally at `.test-tmp/final-suite.log` (ignored scratch; not part of the repository). No new GitHub Actions run is claimed for this local branch. The existing workflow runs the expanded test runner when the branch is subsequently submitted.

## Still required before promotion

- Independent review of the implementation and pinned dependency.
- Deeper decoded-data compatibility comparisons, beyond no-op binary equality on the generated fixture.
- Read-only evaluation against Eric's actual project, with external reports and unchanged-source evidence.
- Separate acceptance of any optional production reader backend. The new audit does not satisfy production mutation gates or authorize structural writing.

See `upstream-adoption.md` for the remaining capability backlog.
