# Third-party notices

The optional Luau executable used as the decoder host is from the
[official Luau project](https://github.com/luau-lang/luau), copyright Roblox
Corporation, and distributed under the MIT License.

The deobfuscator does not redistribute Luau as part of its Python package. Run `python tools/install_luau.py` to download the pinned official release
with SHA-256 verification. A locally downloaded runtime can also be supplied
with `--luau` or selected through `LUAU_PATH`; set `LUAU_COMPILE_PATH` for a
separately installed compiler.
