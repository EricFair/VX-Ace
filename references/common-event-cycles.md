# Direct common-event call cycles

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

A disposable native project was staged through the guarded copy chain with a cycle: a map event calls common event 1, which calls 2, which calls 1. The linter reported one component `[1, 2]` before execution. A bounded test wrapper then ran the project in the real engine: the calls nested through the native interpreter (depths 0, 1, 2) and the wrapper stopped the fourth entry.

This verifies the flagged relationship and increasing native nesting while keeping the test bounded. It does not execute an unguarded infinite loop, measure the engine stack limit or prove behavior with arbitrary custom interpreters.

RTP output protection is described in [asset audit](asset-audit.md).
