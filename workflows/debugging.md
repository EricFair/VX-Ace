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

Trace:

`trigger -> page conditions -> event commands -> switch/variable/self-switch mutations -> common events -> resulting page refresh/transfer/battle state`

Check especially:

- wrong switch/variable ID;
- self-switch on the wrong event/map;
- page priority/order;
- autorun condition never cleared;
- parallel process resetting state repeatedly;
- common event trigger conditions;
- map transfer causing assumptions about local event state to fail.

## C. Feature works in new game but not old save

Suspect:

- new persistent property not initialized in old save;
- database/schema expectation changed;
- one-time setup only occurs during new-game creation;
- serialized object shape differs.

Add safe default/migration logic rather than requiring players to restart unless unavoidable.

## D. Script compatibility bug

Build a method collision table:

| Class | Method | Script A | Script B | Type | Order-sensitive? |
|---|---|---|---|---|---|
| ... | ... | alias/replace | alias/replace | collision | yes/no |

Then reason about call order and side effects. Do not solve compatibility by randomly changing script order without explaining why.
