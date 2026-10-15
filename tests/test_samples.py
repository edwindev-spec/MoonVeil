"""Static checks on the bundled sample (no Luau runtime required)."""
from __future__ import annotations

import unittest
from pathlib import Path

from moonveil.core import analyze, decode_payload, read_source

SAMPLE = Path(__file__).resolve().parent.parent / "samples" / "raw-3.txt"


class RawSampleTests(unittest.TestCase):
    def test_sample_is_recognised_as_supported_v145(self) -> None:
        result = analyze(SAMPLE)
        self.assertEqual(result.version, "1.4.5")
        self.assertTrue(result.supported)
        self.assertEqual(result.payload_bytes, 21664)
        self.assertIn("custom VM dispatcher", result.layers)

    def test_sample_payload_decodes(self) -> None:
        self.assertEqual(len(decode_payload(read_source(SAMPLE))), 21664)


if __name__ == "__main__":
    unittest.main()
