# SPDX-FileCopyrightText: 2026 roolrz
# SPDX-License-Identifier: Apache-2.0

import importlib.util
import lzma
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("build", ROOT / "scripts/build.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class BuildTests(unittest.TestCase):
    def test_compression_preserves_image(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            image = directory / "disk.img"
            image.write_bytes(b"partition table fixture" + bytes(65536))
            digest = build.compress_image(image, directory, "sd")
            with lzma.open(directory / "hyper-rpi5-sd.img.xz", "rb") as stream:
                self.assertEqual(stream.read(), image.read_bytes())
            self.assertEqual(digest, build.sha(image))

    def test_release_build_excludes_local_overrides(self):
        environment = {
            "PATH": "/usr/bin",
            "IO_VM_PACKAGE": "/local/io",
            "RPI5_BOOT_PACKAGE": "/local/boot",
            "BOARD_CONFIG": "/local/board",
            "NATIVE_IMAGE_PROFILE": "test",
            "MAKEFLAGS": "-e",
            "MAKEOVERRIDES": "ARCH=x86_64",
        }
        with (
            patch.dict(build.os.environ, environment, clear=True),
            patch.object(build, "run") as run,
        ):
            target = build.build_image(Path("/checkout"), "sd")
        self.assertEqual(target, "rpi5-sd")
        self.assertEqual(run.call_args.kwargs["env"], {"PATH": "/usr/bin"})
        self.assertEqual(run.call_args.kwargs["cwd"], Path("/checkout"))
        self.assertEqual(
            run.call_args.args,
            ("make", "rpi5-sd", "ARCH=aarch64", "BOARD_IMAGE_REPLACE=--replace"),
        )


if __name__ == "__main__":
    unittest.main()
