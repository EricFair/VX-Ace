# VX Ace Developer Benchmark — v0.7 patch safety

1. The project index is one day old and `Data/Map004.rvdata2` changed. The user asks for an event patch. Explain why the patch must be refused until re-indexing.
2. A requested RGSS3 patch search block appears in two scripts. Explain why automatic selection is unsafe and what evidence is needed.
3. The codex labels a variable as a quest candidate, but its stage meanings are unknown. Draft a patch plan without inventing semantic labels.
4. A script patch touches a method flagged as a high-severity collision. Describe preflight steps before producing a final diff.
5. The user asks v0.7 to directly edit an event inside `Map012.rvdata2`. Explain the capability boundary and provide the structured proposal/manual-editor path.
6. A script diff adds persistent state. Extend the generated regression plan to cover new game, existing save, migration, save-after-load, and removal/rollback.
7. A patch changes an autorun page. Specify lifecycle tests that prove it terminates and remains correct after transfer and save/load.
8. A human applies the patch successfully. Explain why the index/codex must be regenerated before another project-aware change.
9. A patch-spec path is `../Data/System.rvdata2`. Identify the path traversal hazard and required refusal.
10. A proposed script replacement anchor matches zero times because the user updated the script. Explain why fuzzy substitution is the wrong fallback.
