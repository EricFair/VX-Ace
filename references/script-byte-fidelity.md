# Exact UTF-8 script exports and multiline anchors — v0.21

Use this when extracting RGSS3 source or preparing exact multiline replacements, especially on Windows. Generate a new external index with the updated reader; old indexes are not rewritten automatically.

The reader now writes verified UTF-8 source bytes directly, preserving CRLF, LF, bare CR and mixed line endings. The Ruby bridge records each source's SHA-256, byte count, UTF-8 decodability, ASCII-subset observation and newline counts in `scripts/order.json`. Python verifies the bridge observations before writing the exported `.rb`. These describe bytes, not proof of runtime compatibility or the original declared code page.

Previously, Windows text-mode output added a carriage return to existing CRLF script lines. One native Main source had 367 archive bytes but 374 exported bytes, with seven doubled carriage returns. Multiline anchors and indexed line numbers could consequently disagree with the actual script. Do not repair existing source projects or normalize their archives to work around that old export issue; re-index externally.

The planner and copy audit now read indexed script bytes without universal-newline conversion. Search anchors remain exact and unique; no fuzzy newline fallback is added. When building a spec programmatically, preserve the captured bytes:

```python
source = script_path.read_bytes().decode("utf-8", "strict")
# Select an exact, unique block from source. JSON preserves its \r\n escapes.
spec = {"changes": [{"kind": "script", "script_path": script_path.name,
                     "search": exact_block, "replace": reviewed_replacement}]}
```

An LF-only anchor does not match a CRLF block. Replacements intentionally use the supplied exact bytes; keep the chosen source convention when editing. The existing source/index freshness, complete project and immediate target byte gates, disposable copy, re-index/diff and native runtime review remain required.

Script extraction no longer replaces invalid UTF-8 bytes or corrupt compressed source with guessed text or placeholder comments. Invalid/truncated/trailing zlib streams, unsupported source encoding and invalid archive entries produce a partial/error reader result. An index reporting extraction errors is refused by the copy patcher, even if a database-only mutation target itself would round-trip. No code-page conversion is guessed; preserve the original archive and investigate its actual encoding separately.

Script extraction bounds are 4096 entries, 16 MiB compressed/decompressed per source and 64 MiB decompressed source total. Inflation is incremental with bounded input chunks. These are tool admission limits, not RGSS3 engine limits or an OS security sandbox. Database/string presentation outside Script Editor sources retains its existing separate behavior.

Five regression tests cover exact CRLF/LF/mixed and non-ASCII UTF-8 bytes, metadata, exact multiline planner/copy behavior, bad/trailing/truncated deflate, non-UTF-8 refusal, partial-index mutation refusal and inflation budgets. Public fixtures are original authored source. Proprietary scripts and native test projects remain private.

All 126 scripts from the private native seed matched their decompressed archive bytes exactly after fresh extraction. A private CRLF block was staged into one disposable baseline, then replaced by an exact multiline spec into another copy; actual VX Ace startup executed the replacement marker and reached the title normally. No source project or proprietary script text was published.
