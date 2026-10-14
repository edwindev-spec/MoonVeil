"""Real compiler/runtime tests, using only synthetic fixtures."""
from __future__ import annotations

import contextlib
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from moonveil.cli import main
from moonveil.core import MoonVeilError, analyze
from moonveil.errors import MoonVeilTimeoutError
from moonveil.runtime import find_compiler, find_luau
from moonveil.tracing import _run_instrumented_text, canonical_external_trace
from moonveil.v145_cleanup import _remote_loader, emit_readable_luau
from moonveil.v145_pipeline import _compile_text, recover_v145
from moonveil.v145_source import _fold_arithmetic

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests/fixtures/source_level.lua"


def ir(instructions):
    return {
        "schema": "moonveil-v145-semantic-ir-v2",
        "prototypes": [{"name": "P0", "parameter_count": 0, "stack_size": 6, "nested": [],
                        "instructions": [dict(pc=index, **op) for index, op in enumerate(instructions)]}],
    }


class SemanticRegressionTests(unittest.TestCase):
    def test_arithmetic_leaves_strings_and_comments_unchanged(self):
        source = 'local a = 6*7; local b = "6*7" -- 6*7\nlocal c = [=[6*7]=]'
        result, count = _fold_arithmetic(source)
        self.assertEqual(count, 1)
        self.assertEqual(result, source.replace('a = 6*7', 'a = 42'))

    def test_arithmetic_never_folds_a_dynamic_expression_substring(self):
        for source in ("local y = x*2+3", "local y = x+2*3", "local y = 2+3*x", "local y = 2+3^x"):
            with self.subTest(source=source):
                self.assertEqual(_fold_arithmetic(source), (source, 0))
        self.assertEqual(_fold_arithmetic("return 6*7"), ("return 42", 1))

    def test_trace_normalizes_posix_source_locations(self):
        left = '/tmp/original.luau:12: bad call'
        right = '/tmp/recovered.luau:99: bad call'
        self.assertEqual(canonical_external_trace(f'MVTASKDONE\tfalse\t{left.encode().hex()}'),
                         canonical_external_trace(f'MVTASKDONE\tfalse\t{right.encode().hex()}'))

    def test_remote_loader_requires_proven_register_flow_and_empty_return(self):
        program = ir([
            {"op": "GETIMPORT", "a": 0, "path": ["loadstring"]},
            {"op": "GETIMPORT", "a": 1, "path": ["game"]},
            {"op": "LOAD", "a": 3, "value": "https://example.invalid/test"},
            {"op": "NAMECALL", "a": 1, "b": 1, "key": "HttpGet"},
            {"op": "CALL", "a": 1, "b": 3, "c": 0},
            {"op": "CALL", "a": 0, "b": 0, "c": 2},
            {"op": "CALL", "a": 0, "b": 1, "c": 1},
            {"op": "RETURN", "a": 0, "b": 1},
        ])
        self.assertIsNotNone(_remote_loader(program))
        operations = program["prototypes"][0]["instructions"]
        operations[2]["a"] = 5
        self.assertIsNone(_remote_loader(program))
        operations[2]["a"] = 3
        operations[-1]["b"] = 2
        self.assertIsNone(_remote_loader(program))


class LuauIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.luau = find_luau(None, ROOT)
            if find_compiler(cls.luau) is None:
                raise MoonVeilError("Luau compiler required for integration tests")
        except MoonVeilError as exc:
            if os.environ.get("MOONVEIL_REQUIRE_LUAU") == "1":
                raise
            raise unittest.SkipTest(str(exc))

    def execute(self, source):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "program.luau"
            path.write_text(source)
            result = subprocess.run([str(self.luau), str(path)], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout

    def test_source_level_recovery_preserves_stdout(self):
        result = recover_v145(FIXTURE, luau_path=self.luau, timeout=5)
        self.assertTrue(result.verification["compiled"])
        self.assertEqual(result.verification["static_string_replacements"], 8)
        self.assertEqual(self.execute(result.recovered_source), self.execute(FIXTURE.read_text()))

    def test_analyze_uses_available_compiler_for_truncated_input(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "truncated.lua"
            source.write_text(FIXTURE.read_text() + '\nlocal function unfinished(')
            result = analyze(source)
            self.assertFalse(result.supported)
            self.assertIn("truncated", " ".join(result.notes))
            with self.assertRaisesRegex(MoonVeilError, "truncated or incomplete"):
                recover_v145(source, luau_path=self.luau, timeout=5)

    def test_cli_writes_compiled_output_and_manifest(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "recovered.luau"
            artifacts = Path(directory) / "artifacts"
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(["decompile", str(FIXTURE), "-o", str(output), "--luau", str(self.luau), "--artifacts", str(artifacts)])
            self.assertEqual(code, 0)
            manifest = json.loads((artifacts / "decompile_manifest.json").read_text())
            self.assertTrue(manifest["verification"]["compiled"])
            self.assertIsNone(manifest["verification"]["equivalent"])
            self.assertEqual(manifest["input"]["sha256"], analyze(FIXTURE).sha256)
            self.assertEqual(self.execute(output.read_text()), self.execute(FIXTURE.read_text()))

    def test_compiler_reports_invalid_generated_source(self):
        result = _compile_text('local function (', source_path=FIXTURE, luau_path=self.luau, timeout=5, label="test")
        self.assertFalse(result["compiled"])
        self.assertTrue(result["diagnostic"])

    def test_trace_runtime_errors_are_not_successful_empty_traces(self):
        with self.assertRaisesRegex(MoonVeilError, "exited with code"):
            _run_instrumented_text('error("broken")', source_path=FIXTURE, luau_path=self.luau, prefix="moonveil-test", timeout=5)

    def test_runtime_timeout_is_typed(self):
        with self.assertRaises(MoonVeilTimeoutError):
            _run_instrumented_text('while true do end', source_path=FIXTURE, luau_path=self.luau, prefix="moonveil-test", timeout=0.05)

    def test_structured_arithmetic_and_call(self):
        source, profile = emit_readable_luau(ir([
            {"op": "GETIMPORT", "a": 0, "path": ["print"]},
            {"op": "LOAD", "a": 1, "value": 42},
            {"op": "CALL", "a": 0, "b": 2, "c": 1},
            {"op": "RETURN", "a": 0, "b": 1},
        ]))
        self.assertEqual(profile, "structured")
        self.assertEqual(self.execute(source), "42\n")

    def test_structured_conditional_preserves_branches(self):
        for value, expected in ((True, 'yes\n'), (False, 'no\n')):
            program = ir([
                {"op": "GETIMPORT", "a": 0, "path": ["print"]},
                {"op": "LOAD", "a": 1, "value": value},
                {"op": "COMPARE_CONST", "a": 1, "operator": "==", "value": True, "true_target": 3, "false_target": 5},
                {"op": "LOAD", "a": 1, "value": "yes"},
                {"op": "JUMP", "next": 6},
                {"op": "LOAD", "a": 1, "value": "no"},
                {"op": "CALL", "a": 0, "b": 2, "c": 1},
                {"op": "RETURN", "a": 0, "b": 1},
            ])
            source, profile = emit_readable_luau(program)
            self.assertEqual(profile, "structured")
            self.assertEqual(self.execute(source), expected)
