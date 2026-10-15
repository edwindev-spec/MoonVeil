"""Coverage for the doctor command, multi-file analyze and CLI error handling."""
from __future__ import annotations

import contextlib
import io
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from moonveil import __version__
from moonveil.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "source_level.lua"


def run(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class DoctorTests(unittest.TestCase):
    def test_reports_missing_runtime(self) -> None:
        with patch.dict(os.environ, {"LUAU_PATH": "", "LUAU_COMPILE_PATH": ""}), patch(
            "moonveil.runtime.shutil.which", return_value=None
        ), patch("moonveil.runtime._executable", return_value=None):
            code, out, _ = run(["doctor", "--json"])
        report = json.loads(out)
        self.assertEqual(code, 2)
        self.assertFalse(report["ready"])
        self.assertIsNone(report["luau"])
        self.assertEqual(report["moonveil"], __version__)
        self.assertTrue(report["problems"])

    def test_invalid_explicit_runtime_is_a_problem_not_a_crash(self) -> None:
        code, out, _ = run(["doctor", "--json", "--luau", "/definitely/not/luau"])
        self.assertEqual(code, 2)
        self.assertIn("not an executable file", json.loads(out)["problems"][0])

    @unittest.skipIf(os.name == "nt", "uses a POSIX shell script as a fake runtime")
    def test_ready_with_fake_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory) / "luau"
            fake.write_text("#!/bin/sh\necho 'Luau 0.0-test'\n")
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            with patch.dict(os.environ, {"LUAU_COMPILE_PATH": ""}):
                code, out, _ = run(["doctor", "--json", "--luau", str(fake)])
        report = json.loads(out)
        self.assertEqual(code, 0)
        self.assertTrue(report["ready"])
        self.assertEqual(report["luau_version"], "Luau 0.0-test")


class AnalyzeManyTests(unittest.TestCase):
    def test_single_input_keeps_object_shape(self) -> None:
        code, out, _ = run(["analyze", str(FIXTURE), "--json"])
        self.assertEqual(code, 0)
        self.assertIsInstance(json.loads(out), dict)

    def test_many_inputs_return_list_and_report_failures(self) -> None:
        missing = str(FIXTURE.parent / "missing.lua")
        code, out, err = run(["analyze", str(FIXTURE), missing, "--json"])
        records = json.loads(out)
        self.assertEqual(code, 2)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["version"], "1.4.5")
        self.assertIn("error", records[1])
        self.assertIn("missing.lua", err)

    def test_many_inputs_all_good(self) -> None:
        code, out, _ = run(["analyze", str(FIXTURE), str(FIXTURE)])
        self.assertEqual(code, 0)
        self.assertEqual(out.count("version:"), 2)


class ErrorBoundaryTests(unittest.TestCase):
    def test_unexpected_error_is_summarised(self) -> None:
        with patch("moonveil.cli.analyze", side_effect=ValueError("boom")):
            with patch.dict(os.environ, {"MOONVEIL_DEBUG": ""}):
                code, _, err = run(["analyze", str(FIXTURE)])
        self.assertEqual(code, 1)
        self.assertIn("unexpected ValueError: boom", err)
        self.assertNotIn("Traceback", err)

    def test_debug_flag_propagates_unexpected_error(self) -> None:
        with patch("moonveil.cli.analyze", side_effect=ValueError("boom")):
            with self.assertRaises(ValueError):
                run(["--debug", "analyze", str(FIXTURE)])

    def test_recursion_error_is_a_clean_failure(self) -> None:
        with patch("moonveil.cli.analyze", side_effect=RecursionError()):
            with patch.dict(os.environ, {"MOONVEIL_DEBUG": ""}):
                code, _, err = run(["analyze", str(FIXTURE)])
        self.assertEqual(code, 2)
        self.assertIn("nested too deeply", err)


if __name__ == "__main__":
    unittest.main()
