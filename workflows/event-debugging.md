# Event debugging workflow

## Step 1 — Identify active page

Do not start by reading the visible event commands. First determine which page is actually active.

Inspect page conditions from highest page downward.

## Step 2 — Inspect trigger

Determine whether the active page is:

- Action Button;
- Player Touch;
- Event Touch;
- Autorun;
- Parallel Process.

The trigger changes which interpreter owns the execution and what can block other logic.

## Step 3 — Capture state

Record relevant:

- switches;
- variables;
- self switches;
- inventory items;
- actor-in-party conditions;
- map ID/event ID;
- quest stage.

## Step 4 — Trace writers

Find where the prerequisite state should have been changed. Do not assume the displayed event is the writer.

## Step 5 — Check transfers and refresh

If the bug appears after transfer or state changes mid-map, verify the new map/page state is refreshed and that no sequence expected the old map interpreter to continue.

## Step 6 — Common events

If a common event is involved, inspect:

- trigger type;
- activation switch;
- caller/reservation source;
- whether it assumes `This Event` context;
- whether nested event calls can recurse unexpectedly.

## Step 7 — Parallel/autorun contention

Disable or gate suspected autorun/parallel events one at a time to isolate contention.

## Step 8 — Minimal fix

Fix the ownership/state transition rather than adding an extra parallel checker to compensate.

## Regression test

Re-run the path from the earliest prerequisite, not only from a save made immediately before the bug.
