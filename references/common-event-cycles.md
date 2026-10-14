# Direct common-event call cycles — v0.16

The existing read-only event linter now builds a bounded graph of native `117` Call Common Event commands. It reports exact strongly connected components containing mutual calls or self-calls as `possible_common_event_recursion` warnings. It does not change or block event commands automatically.

```powershell
python tools/vxace_event_lint.py PROJECT_INDEX --project PROJECT --output NEW_EXTERNAL_REPORT
```

Use a fresh complete index and a new external output directory. The normal source/index integrity checks remain mandatory. Common-event IDs must match their native array slots; malformed/ambiguous owners refuse analysis. Invalid call parameter shapes are warnings with partial coverage; absent positive targets are reported separately from cycles. Under the default interpreter, an absent target does not create a child event.

## Reading the result

`common_event_graph` reports common-event node count, direct common-event call sites/unique edges, map/troop entry call sites, cyclic component count and opaque call count. Map and troop entry sites are not common-event nodes. Unused common events are still inspected.

Each cycle warning includes its common-event IDs, exact evidence for one call, total internal call-site count and up to 40 detailed evidence samples. Truncation is explicit. An acyclic downstream common event is excluded from the cycle component. The graph walk is iterative, so a long valid graph does not depend on Python's recursion depth; input, graph, walk and finding budgets still apply.

Calls within branches are included as possible edges. Conditions, switches, scripts, exits and earlier commands can prevent or bound recursion. Script-generated calls and dynamically replaced common events are outside the graph. No warning does not establish termination, and a warning does not establish that an infinite loop will occur. The legacy `coverage_complete` field concerns recognized diagnostic data/schema, not a whole-game control-flow proof.

## Native verification and limits

Fifteen automated tests cover self/mutual/disconnected cycles, acyclic chains, downstream exclusion, conditional uncertainty, missing/opaque targets, native ID-slot agreement, bounded evidence, map/troop entries, stale/source integrity, deep iterative graphs and budget refusal.

A private disposable native project was staged through the guarded Python copy chain: map event 1 calls common event 1; common event 1 calls 2; common event 2 calls 1. Exact snapshots, source/index freshness, all 16 byte gates, re-index, semantic review, copied native version advancement and all 16 post-copy byte gates passed. The linter reported one component `[1, 2]` before execution.

The same transaction installed a private Main-slot test wrapper that logs each entry into the native Call Common Event command and stops the fourth entry. Actual VX Ace F12 playtesting produced target/depth/count rows `1/0/1`, `2/1/2`, `1/2/3`, `2/3/4`, then returned to the map message “Bounded common-event cycle test finished.” The first three entries used the native nested interpreter path; the fourth was intercepted by the guard.

This verifies the flagged relationship and increasing native nesting while keeping the test bounded. It does not execute an unguarded infinite loop, measure the engine stack limit or prove behavior with arbitrary custom interpreters. The guard and project data are private test artifacts, absent from the delivered village and public skill examples. The original project remains unchanged.

## RTP output protection

v0.16 also refuses standalone asset reports and master output anywhere inside an explicit RTP root, before creating report directories. The RTP is a read-only input just like the game and index. Regression tests verify that these refusals leave it unchanged. This closes an output-path gap in the v0.15 wrappers; the actual v0.15 validation used an external report directory and did not write into RTP.
