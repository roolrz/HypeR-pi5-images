# SPDX-FileCopyrightText: 2026 roolrz
# SPDX-License-Identifier: Apache-2.0

import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import materials


class MaterialsTests(unittest.TestCase):
    def test_apk_source_identity(self):
        text = "P:busybox-binsh\nV:1.37.0-r30\nL:GPL-2.0-only\no:busybox\nc:" + "a" * 40
        package = materials.apk_packages(text)[0]
        self.assertEqual(package["o"], "busybox")
        with self.assertRaisesRegex(ValueError, "incomplete"):
            materials.apk_packages("P:busybox\nV:1.37.0-r30")
        with self.assertRaisesRegex(ValueError, "empty"):
            materials.apk_packages("")

    def test_recipe_checksums_do_not_execute_shell(self):
        digest = "a" * 128
        self.assertEqual(
            materials.recipe_checksums(f'sha512sums="\n{digest}  source.tar.gz\n"'),
            {"source.tar.gz": digest},
        )
        self.assertEqual(materials.recipe_checksums("pkgname=alpine-base\n"), {})
        with self.assertRaisesRegex(ValueError, "no literal"):
            materials.recipe_checksums(
                'source="upstream.tar.gz"\nsha512sums=$(generate)'
            )
        for name in ("../escape", "..", "/absolute"):
            with self.assertRaisesRegex(ValueError, "invalid"):
                materials.recipe_checksums(f'sha512sums="{digest}  {name}"')

    def test_bad_download_preserves_previous_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "source.tar"
            path.write_bytes(b"previous")
            expected = hashlib.sha256(b"expected").hexdigest()
            with patch.object(
                materials.urllib.request, "urlopen", return_value=io.BytesIO(b"wrong")
            ):
                with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                    materials.fetch("https://example.invalid/source", path, expected)
            self.assertEqual(path.read_bytes(), b"previous")
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_verified_cache_needs_no_network(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "source.tar"
            path.write_bytes(b"verified")
            with patch.object(materials.urllib.request, "urlopen") as request:
                materials.fetch(
                    "https://example.invalid/source", path, materials.digest(path)
                )
                request.assert_not_called()

    def test_libc_materials_reject_another_appliance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "scripts").mkdir()
            (root / "scripts/io-vm.lock.json").write_text(
                json.dumps(
                    {
                        "platforms": {
                            "rpi5": {
                                "reference": "example@sha256:new",
                                "source_revision": "new",
                            }
                        }
                    }
                )
            )
            with self.assertRaisesRegex(ValueError, "I/O VM changed"):
                materials.collect_libc(
                    root,
                    root / "output.tar.gz",
                    root / "cache",
                    {"io_manifest_sha256": "old", "source_revision": "old"},
                )
            self.assertFalse((root / "output.tar.gz").exists())


if __name__ == "__main__":
    unittest.main()
