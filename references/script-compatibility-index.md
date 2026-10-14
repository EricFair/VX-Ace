# Script Compatibility Index

v0.4 introduces a machine-generated compatibility index for extracted RGSS3 scripts.

## Why this exists

VX Ace commonly combines many scripts by reopening the same classes and aliasing existing methods. Two scripts can both be individually correct but conflict because:

- both replace the same method;
- one expects to load after another;
- an alias captures a method before/after a different script changes it;
- both claim the same `$imported` key;
- both modify save content without preserving the other script's data;
- both parse the same note syntax differently;
- both assign a shared constant/global differently.

The analyzer converts those relationships into structured evidence before the agent edits anything.

## Core entities

### Script

Records path, deterministic load order, classes/modules opened, methods defined, aliases, imported keys, constants, globals, save hooks, and note parsing.

### Method symbol

Represented as:

```text
ClassName#method_name
ClassName#self.singleton_method
```

A collision candidate is emitted when more than one script defines the same symbol.

### Alias relationship

Common VX Ace extension pattern:

```ruby
alias my_feature_update update
def update
  my_feature_update
  # extension
end
```

A visible alias of the prior method lowers—but does not eliminate—collision risk.

### `$imported` dependency

Many script ecosystems use:

```ruby
$imported["Some-Core"] = true
```

and later:

```ruby
if $imported["Some-Core"]
```

The index checks whether a key is never defined or only defined later in script order.

## Agent workflow

Before changing a method:

1. Search the compatibility index for that class/method.
2. Inspect every script that defines or aliases it.
3. Respect Script Editor order.
4. Determine the expected call chain.
5. Prefer an extension point that avoids breaking the chain.
6. Re-run the analyzer after a patch.
7. Regression-test the affected behavior in-engine.

## Important limits

Static analysis cannot prove runtime compatibility. In Ruby, load order and metaprogramming can alter behavior in ways a lexical scanner cannot fully reconstruct.

The index is therefore a **routing and risk-assessment tool**, not a substitute for understanding the involved scripts.
