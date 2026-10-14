# VX Ace Developer Benchmark — v0.2

Thirty scenarios intended to test whether the assistant reasons like a VX Ace developer rather than a generic Ruby assistant.

Score each task with `scoring-rubric.md`.

## A. Architecture selection

1. An NPC gives the player a potion only once. Choose event/database/script architecture and explain why.
2. A locked door opens with either a Key Item or variable `Lockpicking >= 3`. Design the event pages/logic without inventing IDs.
3. The user wants a global “Reputation” value shown in the menu and saved. Choose persistence owner and UI architecture.
4. A boss must change behavior at 50% HP. Decide whether a troop event is sufficient before proposing RGSS3.
5. Every weapon of a certain type should grant a new derived property. Identify the likely engine ownership layer and compatibility risks.

## B. Event/interpreter reasoning

6. An autorun cutscene repeats forever after finishing. Diagnose the most likely structural cause and fix pattern.
7. An event has three pages; page 2 should appear, but page 3 appears instead. Explain page priority and the debugging sequence.
8. A parallel event causes map stutter. Redesign it to avoid unnecessary per-frame work.
9. A self switch set on Map 4/Event 8 does not affect an event with the same numeric ID on Map 5. Explain why.
10. Common Event A calls B and B calls A until the game errors. Identify the interpreter failure class and corrective design.

## C. RGSS3 / engine ownership

11. Add a custom menu screen that can be opened from the main menu and returns correctly. Identify scene/window responsibilities.
12. Add a fourth persistent currency. Explain where state belongs, where UI belongs, and how old saves are handled.
13. Add a skill targeting rule that chooses two random living enemies. Identify the likely action/targeting layer instead of patching Scene_Battle.
14. Change escape probability while leaving battle UI unchanged. Identify the correct subsystem.
15. Change how ATK is derived from equipment only for actors. Choose a narrow likely owner and explain why a global battler patch may be excessive.

## D. Save/load compatibility

16. A script adds `@reputation = 0` in `Game_System#initialize`, then old saves crash on `@reputation + 1`. Explain why and give a migration-safe pattern.
17. A developer stores a `Bitmap` in `$game_system` and saving raises an error. Explain model-vs-presentation persistence boundaries.
18. A script adds a new `contents[:quests]` save key. Design an old-save-safe load path.
19. A custom feature works on new games but not after loading an old save. Give a persistence debugging checklist.
20. Removing a script makes existing saves fail. Explain how to determine whether saved custom classes/objects caused the dependency.

## E. Script compatibility

21. Script A aliases `Game_Action#apply`; Script B later fully replaces `Game_Action#apply`. Explain the effective call chain and why A may stop working.
22. Two battle scripts both replace `BattleManager.process_victory`. Produce a compatibility verdict and integration strategy.
23. A menu add-on requires a core script above it and checks `$imported`. Explain what the agent must inspect before installing it.
24. A patch “works” when placed at the bottom but breaks a save-system script. Explain how to investigate instead of recommending random script order.
25. A script claims MKXP-Z support. The user's game runs standard VX Ace `Game.exe`. Explain the compatibility question the agent must answer before using it.

## F. Debugging / project reasoning

26. A door stops working only after transferring away and back. Trace likely map event/page/self-switch/interpreter causes.
27. A battle crash says `undefined method` on `nil` inside a custom script. List the evidence required before proposing a fix.
28. A menu opens but crashes after closing and reopening several times with a disposed bitmap error. Identify likely resource-lifecycle issues.
29. A new poison mechanic conflicts with an installed Yanfly battle add-on. Describe how to locate method collisions and produce a compatibility patch plan.
30. Given a project index with switch/variable/event references, explain how to trace “boss killed but quest never completes” from troop event to quest-state update to NPC completion page.

## Failure conditions

A response should lose substantial credit if it:

- outputs JavaScript/MV/MZ APIs;
- invents project IDs;
- recommends scripting when a trivial native event/database solution is clearly better;
- claims compatibility without inspecting overlap/order;
- ignores old-save behavior for persistent state;
- patches UI classes for pure game-rule changes or vice versa;
- recommends redistributing copied proprietary default scripts as the skill knowledge base.
