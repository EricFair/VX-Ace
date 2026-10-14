# Quest state machine pattern

For multi-step quests, model progression explicitly rather than scattering unrelated switches.

## Recommended representation

Use one named variable for mutually exclusive linear stages:

```text
Variable: Broken Crown Quest
0 = not started
1 = accepted
2 = crypt discovered
3 = boss defeated
4 = reward claimed
```

Use switches for independent boolean facts that are not simply another value of the same linear state machine.

Examples:

- `Blacksmith Rescued` can coexist with many quest stages -> switch.
- `Broken Crown Quest Stage` has one current stage -> variable.

## Page design

Prefer event pages that correspond to meaningful durable states.

Example quest giver:

- Page 1: variable < 1 -> offer quest.
- Page 2: stage 1 or 2 -> reminder/progress dialogue.
- Page 3: stage 3 -> completion dialogue/reward.
- Page 4: stage >= 4 -> post-quest dialogue.

VX Ace page conditions only support a variable threshold, not arbitrary equality or upper bounds. When one page would accidentally match multiple later stages, use page ordering deliberately or use a conditional branch inside a broader page.

## Monotonic progression

For ordinary linear quests, prefer stage values that only increase. This makes debugging and save migration easier.

If a quest can truly branch, encode the branch deliberately rather than overloading numbers with undocumented meanings.

Example:

```text
0-9   common intro
10-19 ally branch
20-29 rival branch
90    failed
99    complete
```

Document the ranges in the project codex.

## State mutation ownership

Each stage transition should have a clear owner:

- accepting quest -> quest giver event;
- discovering location -> map trigger;
- boss defeated -> troop/post-battle logic;
- claiming reward -> quest giver event.

Avoid multiple events independently writing the same transition unless idempotence is intentional.

## Debug checklist

When a quest stalls:

1. inspect current stage value;
2. identify the event expected to advance it;
3. verify the event page actually became active;
4. check whether a higher page is masking it;
5. verify the correct variable ID/name is written;
6. trace common-event calls;
7. test map refresh/transfer if page state changed while the map was active.
