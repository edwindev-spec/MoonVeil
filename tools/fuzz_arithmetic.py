"""Differential fuzz of the constant folder against a real Lua interpreter.

Usage: python tools/fuzz_arithmetic.py [--count N] [--seed S] [--lua PATH]

Needs any Lua 5.3+ interpreter (lua, lua5.4, lua5.3 or texlua).  Every
expression the folder rewrites is evaluated before and after; the script exits
1 if a result differs by more than 1e-12 (relative).
"""
from __future__ import annotations

import argparse
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from moonveil.v145_source import _fold_code_arithmetic  # noqa: E402

NUMBERS = ["0.0", "1.0", "2.0", "3.0", "7.5", "0.5", "10.0", "255.0", "1e3", "2.5e-2",
           ".5", "4.", "100.0", "0.1", "5.3", "1e15", "1e308", "3", "8", "12", "1e999"]
OPERATORS = ["+", "-", "*", "/", "%", "^"]
LUA_CHECK = r'''
local bad, total = 0, 0
for line in io.lines(arg[1]) do
  local a, b = line:match("^(.-)\t(.*)$")
  local fa, fb = load("return " .. a), load("return " .. b)
  if not fa or not fb then
    bad = bad + 1; print("PARSEFAIL", a, b)
  else
    local _, va = pcall(fa); local _, vb = pcall(fb)
    total = total + 1
    if not (va == vb or (va ~= va and vb ~= vb)) then
      local rel = math.abs(va - vb) / math.max(math.abs(va), 1e-300)
      if not (rel <= 1e-12) then bad = bad + 1; print("MISMATCH", a, b, va, vb) end
    end
  end
end
print("checked", total, "bad", bad)
os.exit(bad == 0 and 0 or 1)
'''


def find_lua(explicit: str | None) -> str:
    for name in ([explicit] if explicit else ["lua", "lua5.4", "lua5.3", "texlua"]):
        found = shutil.which(name) if name else None
        if found:
            return found
    raise SystemExit("no Lua 5.3+ interpreter found; pass --lua")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--count", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--lua")
    args = parser.parse_args()
    rng = random.Random(args.seed)
    pairs: list[tuple[str, str]] = []
    for _ in range(args.count):
        n = rng.randint(2, 5)
        space = rng.choice(["", " "])
        expr = ""
        for index in range(n):
            expr += rng.choice(["", "", "", "-"]) + rng.choice(NUMBERS)
            if index < n - 1:
                expr += space + rng.choice(OPERATORS) + space
        if "--" in expr:
            continue
        folded, count = _fold_code_arithmetic("x = " + expr)
        if count:
            pairs.append((expr, folded[4:]))
    with tempfile.TemporaryDirectory() as directory:
        data, script = Path(directory) / "pairs.tsv", Path(directory) / "check.lua"
        data.write_text("\n".join(f"{a}\t{b}" for a, b in pairs), encoding="utf-8")
        script.write_text(LUA_CHECK, encoding="utf-8")
        return subprocess.run([find_lua(args.lua), str(script), str(data)]).returncode


if __name__ == "__main__":
    raise SystemExit(main())
