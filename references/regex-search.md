# Bounded read-only regex search — v1.1

Use this separate CLI when literal search cannot express the requested text pattern. The existing literal CLI, MCP tools and mutation workflows keep their previous behavior.

```powershell
python tools/vxace_regex_search.py INDEX --project PROJECT --pattern 'Already\s+rewarded[.]' --code 401 --scope events --output NEW_EXTERNAL_REPORT
python tools/vxace_regex_search.py INDEX --project PROJECT --pattern 'gain_(gold|item)' --scope scripts --limit 25 --offset 0 --output NEW_SCRIPT_REPORT
```

Output is `regex-search.json`. Require a fresh complete Project Reader index and current source project. Shared index/source hash checks, path/link refusal, work/file/read budgets and new external output rules apply. A malformed pattern, deadline, oversized input/result or stale/changed data returns exit2 and no complete report; a successful scoped search returns exit0, including zero matches. No game files, saves, Ruby scripts or formulas are executed or modified.

## Matching and evidence

Patterns use Python's `re` syntax, not RGSS3 Ruby regex syntax. The pattern must be nonempty, single-line and at most512 characters. Default matching uses Python `IGNORECASE`; `--case-sensitive` removes that base flag. Inline flags can override the base behavior. Python regex case matching differs from the literal tool's Unicode case folding: `STRASSE` does not match `Straße` under this regex mode.

The selected scopes, command filter, one-based page/script line and zero-based command/JSON locations follow [literal search](search-and-event-diagnostics.md). The count is the number of matching text fields or script lines, not individual occurrences. Empty matches are allowed. Scripts are searched per line; other normalized text fields can contain multiple lines. `--limit`1..1000 and `--offset`0..100000 bound returned hits while preserving the complete selected-scope total. Excerpts retain the first300 characters and disclose clipping; the match can occur later. Every page rescans the same fresh snapshot.

## Fixed refusal limits

The parent collects text and evidence through the existing bounded read-only index walker. Only the text strings and pattern enter a separate Python `-I -B` matching worker; the worker receives no project/index paths. It does not import project modules or evaluate text as code. This process boundary is a matching deadline and import-isolation control, not a general OS sandbox.

- Fixed10-second worker deadline, including startup, parsing, compilation and matching. The parent terminates/reaps the worker on timeout. Narrow scope/pattern instead of disabling the deadline.
- At most50,000 text candidates,65,536 characters per field/line and4MiB total JSON input, including escaped text/pattern and protocol overhead.
- At most512KiB worker output, with exactly one boolean per input text; malformed, partial or failed responses refuse.
- At most2MiB complete serialized report. Reduce the returned limit for large evidence paths.
- Shared index budgets still apply:500,000 charged steps, depth128,4,096 reads,16MiB/file and128MiB total reads.

Pagination bounds output, not matching work. Exhausting any limit refuses the entire search instead of returning a partial count. Matching finishes before report creation, so a matching timeout creates no report directory. There is no regex option in MCP or automatic diagnostic scans.

## Evidence

Nine focused tests cover exact locations, scope/code/pagination counts, case differences/literal preservation, invalid syntax/strict options, actual catastrophic-pattern termination without a report, text/IPC/output budgets, malformed worker masks, stale/output-path/changed-index refusal and PYTHONPATH import isolation. A fresh private native-project index returned exactly Map1/Event1/Page2/command1/parameters0 for `Already\s+rewarded[.]`; the actual disposable VX Ace game displayed `Already rewarded.` at that event. Existing save/repeat-state assertions and original-project hashes remained unchanged. Keep native projects, extracted text and raw reports private. This is bounded normalized-text coverage, not dynamic/opaque text discovery or gameplay correctness proof.
