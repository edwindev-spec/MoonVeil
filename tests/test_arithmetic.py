"""Constant folding must never change what Lua/Luau would compute."""
from __future__ import annotations

import unittest

from moonveil.v145_source import _fold_code_arithmetic


def fold(code: str) -> str:
    return _fold_code_arithmetic(code)[0]


class FoldedTests(unittest.TestCase):
    def test_basic_precedence_and_associativity(self) -> None:
        self.assertEqual(fold("x = 2 + 3 * 4"), "x = 14")
        self.assertEqual(fold("x = 8 - 3 - 2"), "x = 3")
        self.assertEqual(fold("x = 2 ^ 3 ^ 2"), "x = 512")
        self.assertEqual(fold("x = -2 ^ 2"), "x = -4")
        self.assertEqual(fold("x = 2 ^ -1"), "x = 0.5")

    def test_integer_modulo_uses_floor_semantics(self) -> None:
        self.assertEqual(fold("x = 7 % 3"), "x = 1")
        self.assertEqual(fold("x = -7 % 3"), "x = 2")
        self.assertEqual(fold("x = 7 % -3"), "x = -2")


class NotFoldedTests(unittest.TestCase):
    def assert_unchanged(self, code: str) -> None:
        self.assertEqual(fold(code), code)

    def test_fractional_modulo_is_implementation_specific(self) -> None:
        self.assert_unchanged("x = 5.3 % 0.1")
        self.assert_unchanged("x = 1e15 % 7")

    def test_infinite_operands_are_never_folded(self) -> None:
        self.assert_unchanged("x = 5 % 1e999")
        self.assert_unchanged("x = 5 % -1e999")
        self.assert_unchanged("x = 1e999 - 1e999")

    def test_overflow_and_division_by_zero(self) -> None:
        self.assert_unchanged("x = 1e308 * 10")
        self.assert_unchanged("x = 2 ^ 5000")
        self.assert_unchanged("x = 1 / 0")
        self.assert_unchanged("x = 10 % 0")

    def test_dynamic_neighbours_are_respected(self) -> None:
        self.assert_unchanged("x = a * 2 + 3")
        self.assert_unchanged("x = a + 2 * 3")
        self.assertEqual(fold("x = a - 1\ny = (2 + 3)"), "x = a - 1\ny = (5)")

    def test_negative_result_never_forms_a_comment(self) -> None:
        for code in ("x = a-(1 - 5)", "x = a - (1 - 5)", "x = f(1 - 5)"):
            self.assertNotIn("--", fold(code))
        self.assertEqual(fold("x = a-(1 - 5)"), "x = a-(-4)")


if __name__ == "__main__":
    unittest.main()
