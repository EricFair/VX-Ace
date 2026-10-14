# Workflow — Script Compatibility Review

Use this workflow before declaring that a new RGSS3 patch is safe in an existing VX Ace project.

## 1. Inventory script order

Record every script in execution order, including:

- core/default scripts if extracted for local analysis;
- framework/core scripts;
- battle/menu/input/save systems;
- add-ons/extensions;
- the proposed new patch.

Script order is part of behavior in VX Ace because later class reopenings can replace or wrap earlier methods.

## 2. Identify touched symbols

For the proposed change list:

- classes/modules reopened;
- constants changed;
- methods added;
- methods aliased;
- methods replaced;
- globals read/written;
- note tags/config keys introduced;
- save keys/instance variables introduced.

## 3. Search the project

For every touched method/class, find all other definitions and aliases.

Capture a table like:

| Script | Class | Method | Modification | Load position |
|---|---|---|---|---:|
| CoreBattle | Game_Action | apply | override | 140 |
| ElementAddon | Game_Action | apply | alias | 162 |
| Proposed | Game_Action | apply | alias | 190 |

## 4. Classify collisions

### Low risk

- adding a uniquely named method;
- adding a namespaced module/config constant;
- reading stable public state only.

### Medium risk

- aliasing a method modified by one other compatible wrapper;
- extending a command list through documented hooks;
- adding persistent state to an existing saved object.

### High risk

- replacing a method another script also replaces;
- assuming alias order while another script overwrites after the alias;
- changing core constants used by multiple systems;
- patching `DataManager`, `BattleManager`, `Scene_Battle`, `Game_Action`, `Game_BattlerBase`, or `Game_Interpreter` without inspecting overlaps;
- modifying save format with no old-save path.

## 5. Reason about load order

For aliases, explicitly reason through the chain.

Example:

```text
Default method
  <- Script A alias wraps default
  <- Script B alias wraps Script A
  <- Proposed alias wraps Script B
```

Then consider what happens if any later script performs a full override: it can bypass the entire earlier alias chain.

Do not say “aliases are compatible” in the abstract. Compatibility depends on ordering and semantics.

## 6. Check initialization/dependencies

Look for:

- `$imported` keys;
- constants expected from earlier scripts;
- class existence checks;
- configuration modules;
- script-call APIs;
- note-tag parsers;
- database preprocessing hooks;
- runtime assumptions (MKXP-Z, DLL, resolution patch, mouse/input library).

## 7. Check persistence

If either script adds persistent state:

- inspect `DataManager` hooks;
- check duplicate save-content keys;
- check old-save behavior;
- check custom marshal methods;
- check whether objects stored are serializable.

## 8. Produce a compatibility verdict

Use one of:

- **Compatible — no overlapping behavior found**
- **Likely compatible — overlap is additive/wrapped and order is understood**
- **Conditional — requires this script order/configuration**
- **Conflict — both replace the same behavior**
- **Unknown — source/API not available; cannot responsibly claim compatibility**

Include evidence and the exact scripts/methods involved.

## 9. Regression test

Test the smallest feature interaction matrix rather than only each script alone.

For example, if two scripts affect skills:

```text
baseline skill
skill using Script A feature
skill using Script B feature
skill using both features
save/load with both features
battle transition with both features
```

## Output format

A useful final report:

```text
Compatibility: CONDITIONAL

Overlap:
- Game_Action#apply — Script A aliases it
- Game_Action#apply — Script B replaces it

Risk:
Script B loads after Script A, so A's wrapper is bypassed.

Recommended integration:
Patch Script B's replacement explicitly or move logic to a narrower hook.

Required order:
Core -> Script B -> compatibility patch

Tests:
1. baseline damage
2. A-only effect
3. B-only effect
4. combined effect
5. save/load
```
