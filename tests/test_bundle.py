from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.build_bundle import REPOSITORY_ROOT, build_bundle


class BundleTests(unittest.TestCase):
    def test_bundle_is_reproducible_and_self_describing(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            archive_a, checksum_a = build_bundle(
                REPOSITORY_ROOT, "0.1.0", Path(first)
            )
            archive_b, _ = build_bundle(
                REPOSITORY_ROOT, "0.1.0", Path(second)
            )

            bytes_a = archive_a.read_bytes()
            self.assertEqual(bytes_a, archive_b.read_bytes())

            expected = hashlib.sha256(bytes_a).hexdigest()
            self.assertTrue(checksum_a.read_text(encoding="ascii").startswith(expected))

            with zipfile.ZipFile(archive_a) as archive:
                manifest = json.loads(archive.read("manifest.json"))
                self.assertEqual(manifest["constitution_version"], "0.1.0")
                for item in manifest["files"]:
                    actual = hashlib.sha256(archive.read(item["path"])).hexdigest()
                    self.assertEqual(actual, item["sha256"])

    def test_rejects_non_semantic_version(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            with self.assertRaises(ValueError):
                build_bundle(REPOSITORY_ROOT, "main", Path(output))


if __name__ == "__main__":
    unittest.main()
