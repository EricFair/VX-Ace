# v0.10 Impact / Semantic Verification Benchmark

1. A map event page reads a quest switch and calls a common event. Given a patch targeting that page, identify both dependencies before mutation.
2. A script patch targets a method with a high-severity collision. Escalate the impact report rather than treating the script path as isolated.
3. A database locator references a missing actor ID. Refuse impact analysis instead of inventing the target.
4. A staged patch causes a quest candidate to disappear from the Codex. Surface that as a semantic change requiring review.
5. A graph edge from a switch to an event page disappears after staging. Report the removed dependency.
6. Two Codex snapshots are identical. Report zero semantic changes.
7. A troop-event dependency cannot be fully resolved by the current graph. Report the known evidence plus the limitation rather than claiming completeness.
