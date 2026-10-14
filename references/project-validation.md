# Project Validation Harness — v0.9

`tools/vxace_project_validator.py` is the read-only gate used before treating a real VX Ace project as eligible for v0.8+ copy mutation.

## What it proves

For every `.rvdata2` file currently present under `Data/`, the validator asks the current `rvdata2_mutator.rb` to perform a no-op load/dump into a temporary directory. The file passes only if the temporary output is **byte-for-byte identical** to the original.

This is stronger than merely proving that Ruby can deserialize the file. It demonstrates that the current inert stand-ins and Marshal writer can reproduce that exact file without changing any byte.

A project is marked `copy_mutation_ready=true` only when every discovered `.rvdata2` file passes that gate.

## What it does not prove

- It does not prove that every possible future edit will be semantically correct.
- It does not prove Ruby 1.9.2 runtime compatibility for custom scripts.
- It does not prove third-party scripts are compatible with each other.
- It does not replace testing the staged clone in RPG Maker VX Ace.
- A pass applies to the exact project snapshot and validator/mutator version tested.

## Script syntax diagnostic

If `Scripts.rvdata2` exists, the validator extracts each Script Editor entry through the read-only bridge and runs `ruby -c` using the selected host Ruby.

This is intentionally reported separately from mutation readiness. Host-Ruby parsing can catch obvious syntax corruption, but a modern Ruby parser is **not** equivalent to VX Ace's Ruby 1.9.2 runtime.

## Exit codes

- `0` — every `.rvdata2` file passed the byte-identical gate;
- `3` — one or more files failed round-trip safety and copy mutation should be refused;
- `2` — invalid project/tool/output configuration or validation execution error.

## Output

The validator writes `validation.json` and `validation.md` outside the source project. Persistent output deliberately omits the source project's absolute path.
