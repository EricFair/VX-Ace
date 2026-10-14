# VX Ace Developer Benchmark — v0.1

Do not embed model answers in the skill. These prompts are intended to test behavior across revisions.

## Section A — Engine selection and architecture

1. An NPC should give the player one Potion the first time they speak, then use different dialogue forever. Implement it with the simplest maintainable VX Ace solution.

2. A game has 70 maps, and every map needs access to the same day/night clock. Decide between copied map events, a common parallel event, and RGSS3. Explain the tradeoff and design the maintainable solution.

3. Equipment should grant resistance to a custom `Corruption` mechanic used throughout the game. Decide which parts belong in the database and which, if any, belong in RGSS3.

4. A designer asks for a custom menu page showing faction reputation. Explain the appropriate VX Ace architecture before writing code.

## Section B — Eventing

5. A door opens after a boss is defeated, but after leaving and returning to the map it is closed again. Give a diagnostic path and likely categories of causes without inventing IDs.

6. An autorun cutscene repeats forever and prevents player movement. Explain what to inspect and how to terminate it safely.

7. A map has 80 parallel-process events checking distance to the player every frame and stutters. Redesign the system.

8. A quest spans five maps and three common events. Explain how you would document switch/variable ownership to make it maintainable.

## Section C — RGSS3 correctness

9. Add a persistent integer `reputation` to actors. Explain initialization, access, modification, save behavior, and old-save concerns.

10. Two custom scripts both modify the same `Scene_Battle` method. Describe how you determine whether they are compatible.

11. A requested solution from another AI uses JavaScript and `$gameVariables`. Correct the conceptual error for VX Ace.

12. A script uses syntax available only in much newer Ruby. Explain the compatibility problem and rewrite strategy.

## Section D — Debugging

13. `NoMethodError: undefined method 'foo' for nil:NilClass` appears only when loading old saves. Provide a debugging hypothesis tree.

14. A battle script works until another script is moved above it in the Script Editor. Explain the likely mechanics and investigation method.

15. A state visually appears on an actor but the intended custom damage modifier does not apply. Trace the possible database/default-script/custom-script layers.

16. A common event seems to change the correct variable, but the receiving map event never changes page. List the state and refresh conditions to verify.

## Section E — Project-aware reasoning

For these tasks, assume a project index exists. The model must use provided facts rather than inventing structure.

17. Given a switch reference index, find every writer of `Boss Defeated` before altering its semantics.

18. Given a method index, determine which installed scripts reopen `Game_BattlerBase` and which methods overlap.

19. Given a map-transfer graph, identify maps that can reach `Royal City` without passing the intended story gate.

20. Given a quest codex, diagnose why a boss kill sets Variable 20 while the quest state is documented as Variable 21. Propose the smallest fix and regression tests.

## Target scores

- v0.1 foundation: no formal target; establishes baseline.
- v0.3: >= 75% overall with no engine-confusion failures.
- v0.6: >= 85% overall and >= 80% project-aware section.
- v1.0: >= 90% overall, no section below 85%, validated on real project tasks.
