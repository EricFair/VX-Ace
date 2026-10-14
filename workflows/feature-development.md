# Workflow — Feature Development

## Input

A requested mechanic, UI feature, battle rule, event system, database extension, or project-wide behavior.

## Procedure

### 1. Translate the request into state + behavior

Identify:

- state that must exist;
- events/actions that change it;
- systems that read it;
- UI feedback;
- persistence requirements;
- scope: one map, one actor, battle-only, project-wide, etc.

### 2. Select implementation layer

Evaluate in this order:

1. native database feature;
2. event/common-event/troop-event solution;
3. damage formula or existing editor field;
4. RGSS3 extension;
5. hybrid.

Pick the simplest option that remains maintainable at the project's expected scale.

### 3. Inspect the project

When project files/index are available:

- find existing related systems;
- find relevant switches/variables/common events;
- find custom scripts touching the target classes;
- identify naming and configuration conventions;
- inspect save-data extensions.

### 4. Write an impact map

Record affected:

- database objects;
- maps/events/common events/troops;
- RGSS3 classes/methods;
- scripts and ordering;
- save data;
- UI/assets.

### 5. Implement minimally

Prefer one coherent system over several unrelated patches. Keep content configuration separate from engine logic where practical.

### 6. Test

At minimum test:

- expected normal path;
- feature disabled/not applicable;
- boundary values;
- map transfer if map state is involved;
- battle entry/exit if battle state is involved;
- save + load if persistent state is involved;
- new game and existing save where compatibility matters;
- interaction with identified overlapping scripts.

### 7. Document

Record configuration, IDs/names, script ordering, APIs/script calls, assumptions, and known limitations in the project codex.
