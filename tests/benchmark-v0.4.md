# VX Ace Developer Benchmark v0.4

v0.4 adds script-ecosystem and compatibility-analysis scenarios to the earlier benchmark set.

Score using `tests/scoring-rubric.md`.

## Compatibility-analysis scenarios

### 46. Alias chain versus destructive override

Three scripts define `Game_Battler#item_apply`. The second aliases the previous implementation before redefining it; the third simply redefines it. Explain the load-order risk and identify which transition in the chain is most suspicious.

### 47. Two safe aliases can still conflict

Two scripts both alias `Scene_Battle#use_item` and call their aliases. Explain why "both use aliases" is not enough to guarantee compatibility.

### 48. `$imported` dependency defined later

An addon checks `$imported["Core"]` but Core is below it in the Script Editor. Diagnose the likely behavior and propose the least invasive fix.

### 49. Duplicate `$imported` identity

Two unrelated scripts both assign `$imported["BattleEngine"] = true`. Explain what the analyzer should report and why automatic renaming is unsafe.

### 50. Save-content composition

Two scripts each extend `DataManager.make_save_contents`. One aliases and merges its key; the other replaces the method and returns a fresh hash. Assess the compatibility risk.

### 51. Old-save migration with a compatibility patch

A patch adds a new field to `Game_System`, while an installed save script replaces portions of `DataManager`. Design a migration strategy and test plan.

### 52. Note-tag parser overlap

Two scripts parse `<element rate: ...>` style tags with different formats. Explain what must be inspected before combining them.

### 53. Constant collision

Two scripts assign `BattleManager::MAX_ACTIONS` differently. Explain why this is different from a method collision and how script order affects the result.

### 54. Global variable collision

Two scripts write `$custom_cache` with incompatible object types. Explain what static analysis can detect and what must be verified manually.

### 55. Metaprogramming blind spot

A script uses `class_eval` and `define_method` to replace `Game_Actor#param`. Explain why the lexical analyzer may miss this and how the agent should respond.

### 56. Script order manifest

The extracted script files are named after display names, not numeric order. Explain why filename sorting is unsafe and how an `order.json` changes analysis.

### 57. Compatibility shim design

Two scripts must both affect `Window_Base#draw_actor_hp` but cannot be modified directly. Design a small shim strategy and explain where it should load.

### 58. Framework replacement

A custom battle engine intentionally replaces many `Scene_Battle` methods. The analyzer reports many high-severity collisions against older add-ons. Explain why mass aliasing is not automatically the right fix.

### 59. Analyzer false positive

Two scripts define the same helper method inside two different nested modules that the analyzer accidentally collapses into one scope. Describe how to verify and report the limitation instead of editing code based on a false positive.

### 60. Analyzer report-driven debugging

A battle crash appeared only after adding a new script. The compatibility report shows a new high-severity collision on `Game_Action#make_targets`, plus a late `$imported` dependency. Give a prioritized debugging plan.

## v0.4 pass criteria

A strong result should:

- preserve actual Script Editor order;
- distinguish class reopening from method collision;
- understand common alias chains;
- treat analyzer output as evidence, not proof;
- identify save/load and note-tag collisions as special review areas;
- recognize metaprogramming limitations;
- prefer minimal shims/order fixes over rewriting third-party frameworks;
- include in-engine regression testing.
