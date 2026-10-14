# Damage formula boundaries

VX Ace damage formulas are powerful, but they are not a universal scripting surface.

## Where the formula sits

At a high level the base formula result is evaluated first, then normal engine processing applies relevant modifiers such as element rate, physical/magical rate, recovery rate, critical processing, variance, and guard.

This means a formula should normally express **base value logic**, not reimplement the entire damage pipeline.

## Good uses

A damage formula is appropriate for concise deterministic relationships involving the user (`a`), target (`b`), and game variables (`v`).

Examples of suitable concepts:

- attack minus defense scaling;
- current HP/MP scaling;
- a single quest/system variable affecting magnitude;
- different magnitude based on target state, if concise and readable.

## Warning signs

Graduate to RGSS3 when the formula:

- contains multiple side effects;
- adds/removes many states as hidden behavior;
- changes switches/variables unrelated to damage;
- needs loops or complicated branching;
- duplicates element/critical/variance/guard handling;
- depends on action order or previous actions;
- needs custom targeting;
- needs reusable helper logic across many skills;
- becomes difficult to audit in the database field.

## Side effects

Ruby expressions can technically perform side effects, but that does not make them maintainable. Prefer the skill/item Effects list, common-event effects, or a proper RGSS3 extension for non-damage consequences.

## Custom damage pipeline

If a mechanic needs to alter damage after the formula but before/after standard modifiers, identify the exact desired phase and extend the relevant battler/action method narrowly.

Examples:

- custom element combination -> element-rate stage;
- altered critical multiplier -> critical stage;
- shield applied after defense but before HP loss -> damage construction/execution stage;
- target-selection-dependent scaling -> action/targeting layer plus damage calculation.

## Test matrix

For any custom damage mechanic test:

- physical vs magical;
- critical vs non-critical;
- guarding vs not guarding;
- weakness/resistance;
- variance extremes or zero variance;
- recovery if applicable;
- zero/negative edge cases;
- enemies and actors if both can use it.
