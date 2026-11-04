# Workflow — Debugging

## A. Runtime exception

Collect:

- exact error text;
- exception class;
- script + line;
- call stack;
- action immediately before failure;
- whether it happens on new game, loaded save, or both;
- recently added/reordered scripts.

Then:

1. inspect the failing line;
2. identify the unexpected receiver/value;
3. trace where that value is initialized;
4. check script order and alias chains;
5. check old-save initialization if a new instance variable is nil;
6. make the smallest fix;
7. test all callers of the changed method.

## B. Event logic bug

Follow [event-debugging.md](event-debugging.md): active page, trigger, state, writers, transfers, common events.

## C. Feature works in new game but not old save

Suspect:

- new persistent property not initialized in old save;
- database/schema expectation changed;
- one-time setup only occurs during new-game creation;
- serialized object shape differs.

Add safe default/migration logic rather than requiring players to restart unless unavoidable.

## D. Script compatibility bug

Follow [script-compatibility-review.md](script-compatibility-review.md) (method collision table, load order, persistence). Do not solve compatibility by randomly changing script order without explaining why.
