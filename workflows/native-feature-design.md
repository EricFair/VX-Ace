# Native feature design workflow

Use this workflow before reaching for RGSS3.

## 1. Define durable state

List what must remain true after:

- interaction ends;
- map transfer;
- battle;
- save/load.

Classify each state as self switch, switch, variable, database state/trait, inventory item, or script-owned state.

## 2. Define state transitions

For each transition identify exactly one normal owner.

Example:

```text
Quest giver: 0 -> 1
Cave trigger: 1 -> 2
Boss troop: 2 -> 3
Quest giver: 3 -> 4
```

## 3. Choose editor surface

Ask whether each behavior belongs in:

- page conditions;
- conditional branches;
- common event;
- troop event;
- database effects/traits;
- formula;
- RGSS3.

## 4. Check reusability

If three or more events duplicate the same logical behavior, consider a common event or script abstraction.

Do not abstract unique story content prematurely.

## 5. Check termination

For every autorun/parallel process, prove how and when it stops or yields.

## 6. Check page priority

Document which page should win in every durable state.

## 7. Test lifecycle

Test fresh entry, repeated interaction, transfer away/back, save/load, and later progression states.

## Graduation rule

Move from native eventing to RGSS3 when the editor representation becomes less maintainable than a well-encapsulated system, especially for custom targeting, complex shared data structures, deep UI, or behavior reused across many objects.
