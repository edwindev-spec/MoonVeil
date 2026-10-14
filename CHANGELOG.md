# Changelog

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
