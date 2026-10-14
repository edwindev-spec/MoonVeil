"""Regression coverage for malformed input, portability and file integrity."""
from __future__ import annotations

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from moonveil.cli import build_parser, main
from moonveil.core import MoonVeilError, _VERSION_RE, parse_dump
from moonveil.decoded import parse_decode_protocol
from moonveil.errors import MoonVeilTimeoutError
from moonveil.runtime import find_compiler, find_luau, validate_timeout
from moonveil.storage import write_text
from moonveil.v145_pipeline import _run_core_modes, recover_v145
from moonveil.v145_verify import _compare_traces, verify_alternate_semantic_trace, verify_semantic_trace


def dump(body: str) -> str:
    return f"__MOONVEIL_DUMP_BEGIN_V1__\n{body}\n__MOONVEIL_DUMP_END_V1__"


def decoded(body: str) -> str:
    return f"__MOONVEIL_DECODE_BEGIN_V1__\n{body}\n__MOONVEIL_DECODE_END_V1__"


class ProtocolIntegrityTests(unittest.TestCase):
    def test_invalid_graphs_fail_with_public_error(self):
        for body in (
            "R\tT1\nT\tbanana", "R\tT1", "R\tT1\nT\t1\nT\t1",
            "R\tT1\nR\tT1\nT\t1", "R\tT1\nT\t1\nE\t1\tD1\tT2",
            "R\tT1\nE\t1\tD1\tD2", "R\tT-1\nT\t-1", "R\tZgarbage",
        ):
            with self.subTest(body=body), self.assertRaises(MoonVeilError):
                parse_dump(dump(body))

    def test_cycles_and_binary_strings_are_preserved(self):
        graph = parse_dump(dump("R\tT1\nT\t1\nE\t1\tSff\tT1"))
        entry = graph["tables"][0]["entries"][0]
        self.assertEqual(entry["key"], {"type": "bytes", "hex": "ff"})
        self.assertEqual(entry["value"], graph["root"])

    def test_invalid_decode_records_fail_closed(self):
        for body in (
            "MVDPROTO\t0\t0", "MVDPROTO\t1\t-1", "MVDPROTO\t1\t0\nMVDPROTO\t1\t0",
            "MVDPROTO\t2\t0", "MVDPROTO\t1\t1000000000", "MVDPROTO\t1",
            "MVDPROTO\t1\t0\nMVDINST\t1\t1\t9", "MVDPROTO\t1\t1\nMVDINST\t2\t1\t9",
            "MVDPROTO\t1\t1\nMVDINST\t1\t0\t9", "MVDPROTO\t1\t0\nMVDFIELD\t1\t1\t2\tZ",
        ):
            with self.subTest(body=body), self.assertRaises(MoonVeilError):
                parse_decode_protocol(decoded(body))

    def test_unknown_noise_and_empty_prototypes_are_allowed(self):
        result = parse_decode_protocol(decoded("debug output\nMVDPROTO\t1\t0"))
        self.assertEqual(result["prototypes"][0]["instructions"], [])


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.environment = patch.dict(os.environ, {"PATH": ""}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def executable(self, name):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!/bin/sh\nexit 0\n")
        path.chmod(0o755)
        return path

    def test_finds_linux_tools_in_local_directory(self):
        runtime = self.executable(".tools/luau-0.722/luau")
        compiler = self.executable(".tools/luau-0.722/luau-compile")
        self.assertEqual(find_luau(None, self.root), runtime)
        self.assertEqual(find_compiler(project_root=self.root), compiler)

    def test_invalid_explicit_runtime_does_not_fall_back(self):
        self.executable(".tools/luau-0.722/luau")
        with self.assertRaisesRegex(MoonVeilError, "--luau"):
            find_luau(self.root / "missing", self.root)

    def test_runtime_environment_precedes_bundled(self):
        runtime = self.executable("custom/luau")
        self.executable(".tools/luau-0.722/luau")
        with patch.dict(os.environ, {"LUAU_PATH": str(runtime)}):
            self.assertEqual(find_luau(None, self.root), runtime)

    def test_separate_compiler_environment(self):
        compiler = self.executable("compiler")
        with patch.dict(os.environ, {"LUAU_COMPILE_PATH": str(compiler)}):
            self.assertEqual(find_compiler(project_root=self.root), compiler)

    def test_missing_compiler_is_optional(self):
        with patch("moonveil.runtime.__file__", str(self.root / "moonveil/runtime.py")):
            self.assertIsNone(find_compiler(project_root=self.root))

    @unittest.skipIf(os.name == "nt", "POSIX executable permission check")
    def test_non_executable_runtime_is_rejected(self):
        runtime = self.executable("luau")
        runtime.chmod(0o644)
        with self.assertRaises(MoonVeilError):
            find_luau(runtime, self.root)

    def test_invalid_timeouts(self):
        for value in (0, -1, float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value), self.assertRaises(MoonVeilError):
                validate_timeout(value)
            with self.assertRaises(MoonVeilError):
                recover_v145(self.root / "missing", luau_path=self.root / "missing", timeout=value)

    def test_banner_spellings_and_prerelease(self):
        for text in ("MoonVeil v1.4.5", "moonveil obfuscator V1.4.5", "MoonVeil 1.4.5"):
            self.assertEqual(_VERSION_RE.search(text).group(1), "1.4.5")
        self.assertEqual(_VERSION_RE.search("MoonVeil v1.4.5-beta").group(1), "1.4.5-beta")
        self.assertIsNone(_VERSION_RE.search("MoonVeil v1.4.5oops"))

    def test_every_probe_receives_requested_timeout(self):
        output = decoded("MVDPROTO\t1\t0")
        with patch("moonveil.v145_pipeline.run_decode", return_value=(output, "", object(), object())) as run:
            with patch("moonveil.v145_pipeline.normalize_metadata", return_value={"prototypes": [{"name": "P0"}]}):
                modes, *_ = _run_core_modes(Path("input"), "", {}, luau_path=Path("luau"), timeout=0.5)
        self.assertEqual(len(modes), 7)
        self.assertEqual([call.kwargs["timeout"] for call in run.call_args_list], [0.5] * 7)


class FileSafetyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / "input.lua"
        self.source.write_text("-- MoonVeil v1.4.5\nprint('original')")

    def run_cli(self, args):
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            return main(args)

    def test_commands_cannot_overwrite_input(self):
        original = self.source.read_bytes()
        for command in ("extract", "instrument", "decompile"):
            self.assertEqual(self.run_cli([command, str(self.source), "-o", str(self.source)]), 2)
            self.assertEqual(self.source.read_bytes(), original)

    def test_artifacts_cannot_overwrite_input(self):
        source = self.root / "prototype_graph.json"
        source.write_text("original")
        self.assertEqual(self.run_cli(["decompile", str(source), "-o", str(self.root / "out"), "--artifacts", str(self.root)]), 2)
        self.assertEqual(source.read_text(), "original")

    def test_output_cannot_overlap_artifact(self):
        self.assertEqual(self.run_cli(["decompile", str(self.source), "-o", str(self.root / "semantic_ir.json"), "--artifacts", str(self.root)]), 2)

    def test_hard_link_cannot_overwrite_input(self):
        alias = self.root / "alias.lua"
        os.link(self.source, alias)
        self.assertEqual(self.run_cli(["instrument", str(self.source), "-o", str(alias)]), 2)

    def test_atomic_write_failure_preserves_destination_and_cleans_up(self):
        with patch("moonveil.storage.os.replace", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                write_text(self.source, "replacement")
        self.assertIn("original", self.source.read_text())
        self.assertEqual(list(self.root.glob(".moonveil-*")), [])

    def test_atomic_write_creates_parents_and_preserves_bytes(self):
        destination = self.root / "nested/result.luau"
        write_text(destination, "á\n\x00")
        self.assertEqual(destination.read_bytes(), "á\n\x00".encode())

    def test_cli_rejects_invalid_timeout(self):
        for value in ("0", "-1", "nan", "inf"):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exc:
                build_parser().parse_args(["decompile", "input", "-o", "out", "--timeout", value])
            self.assertEqual(exc.exception.code, 2)


class VerificationTests(unittest.TestCase):
    def test_both_original_wrapper_timeouts_are_inconclusive(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.lua"
            source.write_text("input")
            for alternate in (False, True):
                verifier = verify_alternate_semantic_trace if alternate else verify_semantic_trace
                target = "moonveil.v145_alternate.run_alternate_trace" if alternate else "moonveil.v145_verify._run_instrumented_text"
                with patch("moonveil.v145_verify.instrument_decode", return_value=("", None, None)):
                    with patch(target, side_effect=MoonVeilTimeoutError("timed out")):
                        result = verifier(source, {}, "", luau_path=Path("luau"))
                self.assertIsNone(result["equivalent"])
                self.assertIn("inconclusive", result["note"])

    def test_trace_requires_start_marker(self):
        with self.assertRaises(MoonVeilError):
            _compare_traces("", "", "", "")

    def test_trace_reports_extra_and_changed_events(self):
        marker = "__MOONVEIL_TRACE_BEGIN_V1__\n"
        for left, right in (("MVCALL\ta\t1", "MVCALL\tb\t1"), ("MVCALL\ta\t1", "")):
            result = _compare_traces(marker + left, "", marker + right, "")
            self.assertFalse(result["equivalent"])
            self.assertEqual(result["first_mismatch"], 1)
