# VX Ace Developer Benchmark v0.6 — Project Codex

These 15 tasks extend the previous 75 scenarios to **90 total specialist scenarios**.

Score using `scoring-rubric.md`.

## Codex interpretation

1. `QuestStage` is observed with values 0, 2, and 4 but has no comments/text defining them. Explain what may and may not be concluded.
2. A high-confidence quest candidate links Variable 21, Switch 48, Common Event 14, and three map events. Describe the verification path before changing it.
3. A low-confidence common-event subsystem candidate has one caller. Explain why confidence should not be promoted without more evidence.
4. A codex labels an autorun event as a cutscene candidate. Determine what else must be inspected before changing its termination logic.
5. The user asks “where is this quest completed?” Use a codex/state-machine/evidence workflow rather than guessing from names.

## Relationship graph

6. Trace a map event -> common event -> variable write -> conditional event-page dependency chain.
7. A transfer graph edge points from Map 4/Event 8/Page 2 to Map 17. Explain the difference between source context and destination map.
8. A boss gate candidate shares one event page with Battle Processing and `BossDefeated`. Determine whether the switch is set before or after victory and why that matters.
9. A variable state machine is written from two common events and read on five maps. Propose the safest location to change its semantics.
10. The graph contains a relationship but the referenced map file had a partial extraction error. Explain the confidence/fallback behavior.

## Map/script codex

11. `codex/maps.json` shows an event page touches two switches, a common event, and a transfer. Produce a minimal impact analysis for editing that page.
12. `codex/scripts.json` shows three scripts redefining the same method in Script Editor order. Use codex plus raw source to review compatibility correctly.
13. An event Script command calls `$game_system.quest.advance`, but static script linking cannot resolve the method owner automatically. Explain how to continue investigation.
14. A script collision warning and a quest failure occur in the same feature area. Avoid assuming causation and propose a falsifiable test.
15. After the developer edits three events, decide when the codex must be regenerated and which prior claims become stale.
