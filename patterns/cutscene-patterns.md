# Cutscene patterns

Cutscenes are usually best implemented with event commands unless the project has a custom cinematic framework.

## Basic autorun cutscene

Use an Autorun event only while the cutscene must own player control.

Typical flow:

1. autorun page activates from a switch/quest condition;
2. optional screen fade;
3. movement/dialogue/animation sequence;
4. write durable outcome state;
5. turn off the autorun condition or move to a higher page whose trigger is not Autorun.

**Mandatory rule:** every autorun needs a provable termination path.

A cutscene that ends without invalidating its own autorun condition will restart or monopolize the main map interpreter.

## Local cutscene completion

If the cinematic only matters on this event/map, use a self switch at the end.

If completion changes the broader world, write the relevant global progression switch/quest variable and optionally use a self switch for local presentation state.

## Moving multiple events

Before a long movement sequence:

- confirm target events exist on the map;
- consider `Wait for Completion` behavior;
- account for collision and route failure;
- avoid relying on an event that a higher page may erase or replace midway through the scene.

## Player transfer during cutscene

If the cutscene transfers to another map, do not assume the old map event will continue afterward. Split the sequence into durable stages and let the destination map continue from a switch/variable condition.

Pattern:

```text
Map A autorun
 -> set Cutscene Stage = 2
 -> transfer to Map B

Map B autorun page condition: Cutscene Stage >= 2
 -> continue scene
 -> set Cutscene Stage = 3
 -> terminate autorun
```

## Parallel-process support

Use parallel events for ambient effects or monitoring that genuinely must run alongside normal control. Do not use a parallel process simply to avoid designing proper triggers.

## Skip support

If a project supports cutscene skipping, make the skip path set the same durable final state as the normal path. Never leave the world half-mutated.

## Regression cases

Test:

- entering map before prerequisite;
- entering map with prerequisite;
- saving immediately before scene;
- transfer during scene;
- scene completion and re-entry;
- skip path if present;
- collision-blocked movement;
- party/menu access if the project allows it during cinematics.
