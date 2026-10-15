# Changelog

## 0.13.0

- Add `moonveil doctor` (with `--json`) to report Python, Luau runtime and compiler status; exits 2 when no runtime is usable.
- `moonveil analyze` accepts several files; with `--json` it prints a list and records per-file errors instead of stopping at the first failure. Single-file output is unchanged.
- Add global `--debug` flag and `MOONVEIL_DEBUG` for full tracebacks; unexpected errors now exit 1 with a short message, and deeply nested input exits 2 instead of dumping a traceback.
- `Verify Installation.bat` and CI now run `moonveil doctor`.
- Constant folding no longer rewrites expressions whose result depends on the Lua implementation: fractional `%` (floor formula vs `fmod` differ in rounding) and anything involving infinities (`5 % 1e999` used to become `5`). Integer `%` up to 2^31 is still folded.
- Add `tools/fuzz_arithmetic.py`, a differential fuzz of the folder against a real Lua interpreter (0 mismatches over ~64,000 folded expressions with Lua 5.3).
- Add tests for the new commands, the error boundary and the folding rules.
- Bundle `samples/raw-3.txt` with static regression tests (version, payload size, Base64 decoding).

## 0.12.0

- Import upstream 0.11.0 with MIT attribution and preserve its reconstruction engine.
- Discover native Luau tools on supported platforms and support `LUAU_COMPILE_PATH`.
- Add an official Luau installer with pinned SHA-256 checksums.
- Honor subprocess timeouts and reject nonpositive or nonfinite values.
- Handle timeouts consistently across direct and indirect original wrappers.
- Reject failed trace subprocesses and missing trace markers; normalize POSIX trace paths.
- Validate graph references and decoder prototype/slot declarations before lifting.
- Reject input/output aliases and artifact collisions; replace output files atomically.
- Preserve arithmetic expression boundaries, whitespace, strings and comments.
- Check downloader register dependencies and return semantics before shortening it.
- Add reproducible synthetic tests, real Luau integration checks, cross-platform CI and Spanish usage documentation.
