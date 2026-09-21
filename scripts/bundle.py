#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 roolrz
# SPDX-License-Identifier: Apache-2.0
"""Validate and assemble profile artifacts without rebuilding their images."""

import argparse
import hashlib
import shutil
import tarfile
from pathlib import Path


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_profile(profile):
    if profile.name not in ("pi5-native", "pi5-io-bringup", "pi5-sd"):
        raise ValueError("unknown image profile")
    listed = set()
    for line in (profile / "SHA256SUMS").read_text().splitlines():
        expected, name = line.split("  ", 1)
        if Path(name).name != name or name in listed:
            raise ValueError("invalid checksum filename")
        path = profile / name
        if path.is_symlink() or sha(path) != expected:
            raise ValueError(f"checksum mismatch: {profile.name}/{name}")
        listed.add(name)
    actual = {p.name for p in profile.iterdir()}
    image = f"hyper-r{profile.name}.img.xz"
    if actual != listed | {"SHA256SUMS"} or image not in listed:
        raise ValueError("incomplete profile checksums or missing image")


def bundle(source, output):
    if output.exists():
        raise ValueError("output must be new")
    profiles = sorted(source.glob("pi5-*"))
    if not profiles:
        raise ValueError("no image artifacts")
    # Verify everything before exposing any release assets.
    for profile in profiles:
        verify_profile(profile)
    output.mkdir(parents=True)
    for profile in profiles:
        name = "hyper-r" + profile.name
        image = profile / f"{name}.img.xz"
        shutil.copy2(image, output / image.name)
        with tarfile.open(
            output / f"{name}-materials.tar.xz", "w:xz", preset=0
        ) as archive:
            for path in sorted(profile.iterdir()):
                if path != image:
                    archive.add(path, arcname=path.name, recursive=False)
    root = Path(__file__).resolve().parents[1]
    for name in ("ARTIFACTS.md", "DISTRIBUTION.md"):
        shutil.copy2(root / name, output / name)
    (output / "SHA256SUMS").write_text(
        "".join(f"{sha(p)}  {p.name}\n" for p in sorted(output.iterdir()))
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    bundle(args.input, args.output)
