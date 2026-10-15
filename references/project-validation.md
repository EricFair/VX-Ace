# Project Validation Harness — v0.22 (introduced in v0.9)

`tools/vxace_project_validator.py` is the read-only gate used before treating a real VX Ace project as eligible for v0.8+ copy mutation.

## What it proves

For every `.rvdata2` file currently present under `Data/`, the validator asks the selected backend to perform a no-op load/dump into a temporary directory. The file passes only if the temporary output is **byte-for-byte identical** to the original. Standalone commands default to `rvdata2_mutator.rb`; `--backend python` explicitly selects `vxace_python_mutator.py`. The master configuration selects Python. Never silently fall back between them or reuse readiness across backends.

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

The temporary parser input is the exact verified UTF-8 source: no text-mode newline translation. Each result records `source_sha256`, `source_bytes` and `exact_source_bytes=true`; a source/metadata mismatch refuses parsing that entry. Script names remain presentation labels, not source text. The parser receives only `-c`; it does not run the source. Unsupported encodings require explicit review, never guessed conversion.

Bridge extraction has a 30-second deadline; each host parse defaults to 10 seconds. Standalone `--syntax-timeout 0.1..60` changes the per-script deadline. Timeouts are failed diagnostics, with later entries still checked after a per-script timeout. These bounds cover extraction/parsing only, not round-trip subprocesses, total project duration, output memory or an operating-system sandbox.

This is intentionally reported separately from mutation readiness. Host-Ruby parsing can catch obvious syntax corruption, but a modern Ruby parser is **not** equivalent to VX Ace's Ruby 1.9.2 runtime.

For example, `nil&.to_s` passes modern host Ruby parsing and fails in RGSS3. Never use a successful host parse to skip native testing. Extraction failures still block a complete index and copy-patcher admission under the separate reader gates.

## Exit codes

- `0` — every `.rvdata2` file passed the byte-identical gate;
- `3` — one or more files failed round-trip safety and copy mutation should be refused;
- `2` — invalid project/tool/output configuration or validation execution error.

## Output

The validator writes `validation.json` and `validation.md` outside the source project. Persistent output deliberately omits the source project's absolute path.
