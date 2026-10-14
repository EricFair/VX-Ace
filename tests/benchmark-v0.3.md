# VX Ace Developer Benchmark — v0.3

Forty-five scenarios testing practical VX Ace feature design, native-event discipline, database usage, performance judgment, and escalation to RGSS3.

Score each task with `scoring-rubric.md`.

## A. Native architecture selection

1. A treasure chest gives 500 gold once. Design the smallest maintainable implementation.
2. A door opens permanently after using one consumable key, while another copy of the same key can open a second door. Choose global vs local state correctly.
3. Ten doors all open after one story boss dies. Choose the shared state owner and each door's local state.
4. An NPC changes dialogue after the player recruits Mira, but remains otherwise identical. Decide page-condition versus conditional-branch structure.
5. Three maps use the same healing shrine rules but different visuals. Decide what belongs in a common event and what stays map-local.
6. A shop gains two items after Chapter 3. Decide whether native shop branches/pages are still preferable to scripting.
7. The user asks for a global Reputation value with tiers and menu display. Separate native storage possibilities from the point where RGSS3 becomes justified.
8. A pressure plate opens a nearby gate only while stood upon. Choose transient state/event structure without turning a permanent switch into the owner.

## B. Quest-state architecture

9. Design a five-stage linear quest using one variable instead of five mutually exclusive switches.
10. A quest can branch into ally or rival routes and later converge. Propose a documented stage encoding.
11. The boss dies, but the quest giver still shows pre-boss dialogue. Trace the state machine from troop/post-battle writer to NPC page.
12. A quest variable jumps from 2 back to 1 after visiting another map. Explain how to find the unauthorized writer.
13. Page 3 uses variable threshold `>= 2`; page 4 uses `>= 3`. Explain why stage 3 selects page 4 and how to exploit page priority safely.
14. A quest uses a self switch on the giver for "accepted," but another map needs to know whether it was accepted. Explain the ownership mistake.
15. A quest's completion reward can be claimed twice after a save/load. Design an idempotent completion transition.

## C. Cutscenes and event lifecycle

16. An autorun intro freezes player control forever after the dialogue ends. Diagnose and redesign the termination path.
17. A cutscene transfers from Map A to Map B halfway through. Explain why the old sequence should not be trusted to continue and design a durable stage handoff.
18. A movement route in a cutscene hangs because an NPC cannot reach its target. Give a robust debugging and design approach.
19. A skipped cutscene leaves the boss undefeated flag set incorrectly. Define what the skip path must guarantee.
20. A parallel event exists only to detect `Quest Stage == 3` and turn on another switch once. Replace it with event-driven ownership.
21. Two autoruns become eligible at once on a map. Explain how to reason about contention and deterministic sequencing.

## D. Database, traits, states, skills, equipment

22. A ring should grant 50% poison resistance. Decide whether a native trait is enough before proposing code.
23. A cursed sword grants an attack state and seals one skill type. Choose the database surface.
24. A temporary Berserk effect raises ATK and lowers defense for five turns. Decide whether a state is the natural owner.
25. Every actor of one class should resist Fire by 20%. Choose class trait versus actor/equipment script.
26. A skill should deal normal damage and then apply Blind at 40%. Keep damage and standard effect responsibilities separate.
27. An item should heal and then run a non-battle story hook. Evaluate whether an item common-event effect is appropriate.
28. A new first-class stat "Resolve" is affected by class, equipment, states, UI, and multiple formulas. Explain why native traits may no longer be sufficient and define the script ownership problem.
29. An enemy-only passive should alter targeting priority. Explain why a simple trait may not express it and identify the likely action/unit layer.

## E. Damage-formula boundaries

30. A skill deals `ATK * 4 - DEF * 2` and can crit normally. Keep the formula simple and avoid duplicating standard modifiers.
31. A designer writes a formula that manually multiplies element rate and guard. Explain the double-application risk.
32. A damage formula flips a story switch, adds two states, changes weather, and deals damage. Refactor the responsibilities.
33. A mechanic changes the critical multiplier from x3 to x2 for one class. Decide whether the formula is the right layer and identify the compatibility concern.
34. A skill targets two random living enemies. Explain why custom targeting belongs outside the damage formula.
35. A shield should reduce incoming final HP damage after normal formula/element/critical calculations. Identify the need to choose a precise damage-pipeline phase.

## F. Performance and update discipline

36. A town map has 60 unconditional parallel events each checking one switch every frame. Redesign the architecture.
37. A global day/night system genuinely needs continuous time tracking. Decide whether a gated common parallel event or script subsystem is more maintainable.
38. A custom event script call scans every database item each frame for note tags. Diagnose the cost and propose caching/preprocessing.
39. A map stutters only when several autonomous pathfinding events are active. Give an isolation plan without rewriting the whole project.
40. An ambient torch flicker uses a parallel event with a short Wait. Explain why a parallel process is not automatically wrong.

## G. Escalation to RGSS3 and project reasoning

41. Twenty skills share the same complex conditional side effect. Decide when helper RGSS3 is cleaner than duplicated formulas/common events.
42. A designer wants a custom target-selection UI. Explain why this crosses from database configuration into scene/window/action architecture.
43. A project already has a battle engine that replaces `Game_Battler#make_damage_value`. Explain what must be inspected before adding a shield mechanic there.
44. A native event implementation works but requires 14 duplicated common-event branches keyed by temporary variables. Explain the warning signs that justify a script subsystem.
45. Given a future project index of switch/variable readers and writers, describe how the agent should trace a contradictory quest state without guessing IDs.

## Failure conditions

Substantial penalties apply when a response:

- uses MV/MZ JavaScript or plugin APIs;
- invents project IDs or third-party APIs;
- creates a global switch for purely local event state without justification;
- encodes mutually exclusive linear quest stages as a pile of independent switches without discussing contradictions;
- recommends an autorun without a provable stop condition;
- uses permanent parallel polling for work that can be triggered at state change;
- scripts a mechanic already cleanly expressed by native VX Ace traits/effects;
- hides major side effects inside damage formulas;
- duplicates standard element/critical/variance/guard processing in a formula without a deliberate reason;
- claims script compatibility without inspecting method overlap and load order;
- ignores save/load behavior for durable state.
