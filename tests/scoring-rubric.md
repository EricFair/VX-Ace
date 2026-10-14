# Competency Benchmark Scoring Rubric

Score each task from 0 to 4.

## 4 — Expert

Correct VX Ace-native architecture, technically accurate implementation, state ownership is explicit, compatibility considerations are appropriate, assumptions are not fabricated, and the answer includes useful lifecycle/regression tests.

## 3 — Good

Essentially correct solution with minor omissions that would not normally break the project or create significant maintenance debt.

## 2 — Partial

Plausible but misses an important engine concern, state owner, lifecycle edge case, compatibility issue, or uses unnecessarily invasive architecture.

## 1 — Poor

Shows some relevant knowledge but contains significant VX Ace/RGSS3 mistakes, brittle event design, or would likely require substantial correction.

## 0 — Failure

Wrong engine/API/language, fabricated project facts, unsafe/destructive approach, or does not solve the task.

## Automatic caps

Maximum score 1 if the answer silently uses MV/MZ JavaScript for a VX Ace task.

Maximum score 2 if it provides substantial RGSS3 code but gives no installation/testing guidance where either is necessary.

Maximum score 2 if it invents unprovided project IDs or third-party APIs rather than marking them as placeholders/unknown.

Maximum score 2 if a proposed autorun has no explicit termination condition or a durable transfer/cutscene sequence assumes the old map interpreter will continue after leaving the map.

Maximum score 2 if a linear mutually exclusive progression system is modeled with independent switches without addressing contradictory states.

Maximum score 2 if the answer recommends continuous parallel polling for a one-time reaction that can be owned by the event which changes the state, without explaining why polling is required.

Maximum score 2 if an answer treats a static compatibility finding as proof of incompatibility without inspecting load order, aliases, or the involved implementations.

Maximum score 2 if script-order-sensitive compatibility advice assumes alphabetical/file-system order when the actual VX Ace Script Editor order is available or required.
