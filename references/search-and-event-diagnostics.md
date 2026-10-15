# Read-only search and event diagnostics — v0.13

v1.1 adds a separate [bounded Python-regex CLI](regex-search.md), with fixed-deadline matching and distinct case semantics. The literal commands and MCP interface below retain their behavior.

v0.16 extends the same event linter with [direct common-event call-cycle diagnostics](common-event-cycles.md). Cycles are possible recursion, including conditional or unused calls; no termination proof or automatic fix is implied.

This batch adapts two missing upstream capabilities to our external Project Reader index. It adds no game writer, automatic fix, MCP transport or Ruby execution. The commands require the current source project for freshness/integrity checks and write only new external reports.

## Generate a fresh index

```powershell
python tools/vxace_project_reader.py PROJECT --output NEW_INDEX
```

Use the actual VX Ace project folder or `.rvproj2` file. Keep reports/indexes outside the project. A partial extraction, stale manifest, missing declared decoded file, opaque event list or unsafe linked path is a refusal, not an empty successful result. Reports are private project data; do not publish extracted game text/scripts with the toolchain.

## Search text or native commands

```powershell
python tools/vxace_search.py INDEX --project PROJECT --text "quest text" --output NEW_SEARCH
python tools/vxace_search.py INDEX --project PROJECT --code 117 --output NEW_CALL_SEARCH
python tools/vxace_search.py INDEX --project PROJECT --code 401 --text "welcome" --output NEW_DIALOGUE_SEARCH
python tools/vxace_search.py INDEX --project PROJECT --scope scripts --text "reserve_transfer" --limit 25 --offset 0 --output NEW_SCRIPT_SEARCH
```

Output is `search.json`. Text is a single-line **literal**, up to 512 characters; regular expressions are deliberately unsupported. Matching defaults to Unicode case folding; use `--case-sensitive` for exact case. Code-only search returns one hit per native command; combined code/text search returns matching string fields within commands of that code. No database formula, Script Editor code or embedded script is executed.

Scopes (repeat `--scope` to combine):

- `events`: map/common/troop command parameter strings, with owner/page/command locations.
- `database`: string fields, including names, notes and formulas; excludes command/page/table payloads covered separately or outside text scope.
- `maps`: display names, notes and event names. Map-tree names are also searchable in database MapInfos.
- `scripts`: lines of extracted scripts in exact Script Editor order.

Each hit includes an index-relative file and exact JSON path or script line. Native pages are one-based and command indexes zero-based. Script lines are one-based. `event_scope` distinguishes map/common/troop locations. Excerpts show the first 300 characters of the matched field/line and explicitly indicate clipping; the match can occur later, so inspect the exact evidence path.

`--limit` is 1–1000 (default 100); `--offset` is 0–100000. Results retain the complete count within selected normalized scopes and include `returned`, `truncated`, and `next_offset`. Every page rescans the same fresh snapshot; re-index if the project changes. Result pagination limits returned hits, not the search walk. A zero-match result claims only the documented selected normalized scopes, not all binary/custom data.

## Inspect event logic

```powershell
python tools/vxace_event_lint.py INDEX --project PROJECT --output NEW_EVENT_REPORT
```

Outputs: `event-lint.json` and `event-lint.md`, with exact evidence locations, severity counts and coverage limits. Checks:

- All map/common/troop lists: final root terminator, continuation adjacency, duplicate labels and missing local jump targets. Label comparisons are case-sensitive and confined to one list.
- Map pages: the highest completely observed unconditional page hides every lower page. Conditional higher pages are not automatically treated as permanent shadows. Missing/non-boolean native condition flags produce an explicit coverage warning.
- Highest unconditional map autoruns: warn when no observed release or opaque operation can interrupt the default restart behavior. A common call, script, script-bearing variable/condition, move route, battle call or possible transfer/erase/end-game command produces an informational runtime-review result. Such operations can be unreachable; their presence does **not** prove termination.

`possible_autorun_lock` is a warning under default VX Ace semantics, not a proof against custom interpreter hooks. A self-switch cutscene followed by a conditioned stopping page is not confused with the highest unconditional trap pattern. The tool does not prove general conditional termination, traverse common-event recursion, analyze troop priority, resolve all branches, inspect assets/RTP or automatically repair anything. Opaque commands/conditions make `coverage_complete` false; other unimplemented rules remain explicitly out of scope even when it is true.

Exit codes: lint `0` no warning/error findings (informational runtime-review findings may remain), `3` reviewable warnings/errors, `2` refused/error with no complete report. Search `0` complete result within scope, including zero matches; `2` refused/error. A report's existence is not sufficient: check exit/status and coverage.

## Master integration and safety

`vxace-master.json` enables `event_logic_lint: true`; the read-only master invokes it after successful indexing. A warning changes the master status to `review_required`. `copy_mutation_ready` still describes the independent serialization gate, not clean logic, an approval, or a passing playtest. Turning off an optional diagnostic does not weaken the fixed copy-only mutation policy.

Both CLIs require a hashed fresh Project Reader manifest, recheck source inventory and all read index bytes, reject linked/escaping input and output paths, and refuse existing output directories. The lower-level Python analysis functions operate on an already-selected index; callers needing source freshness must use the shared `execute` transaction or the CLI. These hash checks detect change; they are not filesystem locks or an OS sandbox.

Walk limits: 500,000 charged steps, depth 128, 4,096 reads, 16 MiB per file, 128 MiB total reads; lint permits at most 5,000 findings. Oversized/changed/incomplete inputs refuse instead of claiming exhaustive results. Large projects may need a future separately designed partitioned workflow; do not waive limits or stale checks to force a result.

See [v0.13 validation evidence](real-project-validation-v0.13.md) for native-copy scenarios, automated tests and remaining limits.
