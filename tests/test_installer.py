"""Installer integrity checks with synthetic archives; no network required."""
from __future__ import annotations

import hashlib
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from tools.install_luau import install


class InstallerTests(unittest.TestCase):
    def test_checksum_failure_writes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "tools"
            with patch("tools.install_luau.platform.system", return_value="Linux"), patch("tools.install_luau.platform.machine", return_value="x86_64"):
                with patch("tools.install_luau.urllib.request.urlopen", return_value=io.BytesIO(b"corrupt")):
                    with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                        install(target)
            self.assertFalse(target.exists())

    def test_only_known_verified_files_are_installed(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as bundle:
            bundle.writestr("luau", "runtime")
            bundle.writestr("luau-compile", "compiler")
            bundle.writestr("../unexpected", "should never be extracted")
        archive = buffer.getvalue()
        digest = hashlib.sha256(archive).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "tools"
            with patch("tools.install_luau.platform.system", return_value="Linux"), patch("tools.install_luau.platform.machine", return_value="x86_64"):
                with patch.dict("tools.install_luau.ASSETS", {"Linux": ("synthetic.zip", digest)}):
                    with patch("tools.install_luau.urllib.request.urlopen", return_value=io.BytesIO(archive)):
                        install(target)
            self.assertEqual({p.name for p in target.iterdir()}, {"luau", "luau-compile"})
            self.assertEqual((target / "luau").read_text(), "runtime")
            self.assertFalse((target.parent / "unexpected").exists())
