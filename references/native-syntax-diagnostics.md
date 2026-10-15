# Compile-only native syntax diagnostics — v0.23

Use this optional workflow when modern host parsing cannot answer a Ruby 1.9.2 syntax question. It prepares a **private** source bundle and validates a report from the actual VX Ace runtime. It never launches an application, changes a game, evaluates inspected source or authorizes mutation. The master and MCP remain read-only and do not automatically run this workflow.

## Separate the inspected project and trusted host

The inspected project supplies script bytes. A **different trusted blank editor-created VX Ace seed**, with inspected default scripts and no custom startup code, supplies the disposable runtime host. Never use the inspected custom game as the host: scripts before Main would execute before the diagnostic scaffold. An empty map alone does not establish a trusted script archive. If no trusted host is available, preserve the bundle and obtain one before native execution; never fall back to evaluating the inspected project.

Run normal validation/extraction on both snapshots. Install the scaffold only through the existing guarded disposable-copy workflow. Preserve originals, full project/target byte gates, exact anchors, re-indexing, impact review and audit. This tool does not add a writer or bypass those gates.

## Prepare exact source data

```powershell
python tools/vxace_native_syntax.py prepare INSPECTED_INDEX --project INSPECTED_PROJECT --output NEW_PRIVATE_BUNDLE
```

Use `--ruby HOST_RUBY` when needed. Preparation requires a complete fresh hashed index, a bounded full source inventory and independent native archive extraction. Every indexed entry must match the native order, identity/name and exact UTF-8 source/hash/byte count. It rechecks index/source integrity before writing a new external bundle. Old newline-normalized indexes must be regenerated.

The bundle contains `manifest.json`, `native-syntax-harness.rb` and privacy/staging notes. **The harness embeds exact project source as hexadecimal data. It can contain proprietary/default/custom scripts even though it looks like authored Ruby. Never publish or commit generated bundles, staging specs, native reports or game copies.** The public template and regression fixtures contain authored code only.

## Stage and observe the trusted disposable host

Find the trusted host's exact Main entry and unique start anchor from its fresh byte-preserving index. For the verified default seed, the anchor is `rgss_main { SceneManager.run }`; verify it rather than assuming it exists. Build a normal script replacement spec that inserts the complete generated harness immediately before that anchor. For example, after resolving `host_main_path` and verifying `exact_anchor`:

```python
import json
from pathlib import Path
harness = Path(bundle, "native-syntax-harness.rb").read_bytes().decode("ascii", "strict")
spec = {"changes": [{"kind": "script", "script_path": host_main_path,
                     "search": exact_anchor, "replace": harness + "\r\n" + exact_anchor}]}
Path(spec_path).write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
```

Plan/review and stage with the existing explicit Python copy backend:

```powershell
python tools/vxace_patch_planner.py TRUSTED_HOST_INDEX --project TRUSTED_HOST_PROJECT --spec PRIVATE_SPEC --output NEW_PLAN
python tools/vxace_copy_patcher.py TRUSTED_HOST_INDEX --project TRUSTED_HOST_PROJECT --spec PRIVATE_SPEC --copy NEW_DISPOSABLE_HOST --audit NEW_AUDIT --backend python
```

Check the staged source matches the exact generated scaffold. Open **only the new disposable host** in VX Ace and run F12. The scaffold packs source bytes as data, sets UTF-8 encoding and calls `RubyVM::InstructionSequence.compile`; it never calls `eval`, loads the inspected archive into the running game or evaluates an instruction sequence. It writes the token-named TSV file from the manifest in the disposable host's working directory and exits before Main runs. A title screen is not expected. Existing reports are refused rather than overwritten. Unexpected dialogs, missing reports or an incomplete footer require investigation; do not substitute host Ruby execution for this native step.

## Collect and interpret

```powershell
python tools/vxace_native_syntax.py collect INSPECTED_INDEX --project INSPECTED_PROJECT --bundle PRIVATE_BUNDLE --result NATIVE_HOST_TOKEN_NAMED_TSV --output NEW_PRIVATE_RESULT
```

Collection independently rechecks the current source/index and exact regenerated scaffold. It requires the expected nonce, Ruby `1.9.2`, compiler availability, source hashes/counts/order, bounded statuses/error bytes and a complete footer. Tampered, stale, truncated, duplicate, extra, wrong-runtime or mismatched reports are refused before output. It rechecks report/bundle/index/source inputs before writing `native-syntax.json`.

- Exit0: preparation succeeded, or every collected compile result passed.
- Exit3: a complete native report contains syntax/compiler failures; review each entry.
- Exit2: configuration, freshness, integrity, unsupported compiler or incomplete-report refusal.

`native_parse_report_validated=true` means the local report matches the verified bundle. The tool cannot observe or attest the engine launch; the operator must do that. Local tokens/hashes are evidence bindings, not a cryptographic runtime attestation. `runtime_compatibility_proven=false` and `mutation_authorized=false` always remain: compilation does not establish method availability, dependencies, aliases, load order, native API behavior, gameplay, save compatibility or successful evaluation.

## Bounds and native evidence

Support is limited to 1..4096 UTF-8 entries, 256 KiB each and 4 MiB total source; labels <=512 characters, manifest <=4 MiB, generated scaffold <=9 MiB, result <=16 MiB, each diagnostic <=2048 bytes. These are diagnostic admission limits, not engine limits. Source extraction uses the existing 30-second bridge deadline; native compilation has no per-entry deadline or OS sandbox. Use only disposable hosts and stop/investigate an unresponsive native process. Output collection does not run or stop applications.

The private native seed probe confirmed Ruby1.9.2 compiler availability and modern syntax rejection. All126 seed entries compiled through the generated scaffold and collected successfully. Separate authored trap/error fixtures verify failure reporting and non-execution in native testing. CI checks public scaffold/protocol/refusal behavior with host Ruby and deliberately refuses that host report as native evidence; CI cannot replace the private VX Ace observation.
