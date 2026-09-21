#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 roolrz
# SPDX-License-Identifier: Apache-2.0
"""Compose release assets using only the pinned HypeR build policy."""

import argparse
import hashlib
import importlib.util
import json
import lzma
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import materials

ROOT = Path(__file__).resolve().parents[1]


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def checkout_hyper(lock):
    revision = lock["revision"]
    if (
        not re.fullmatch("[0-9a-f]{40}", revision)
        or lock["repository"] != "https://github.com/roolrz/HypeR.git"
    ):
        raise ValueError("expected an immutable official HypeR commit")
    hyper = ROOT / "work/HypeR"
    if not hyper.exists():
        hyper.mkdir(parents=True)
        run("git", "init", str(hyper))
        run("git", "-C", str(hyper), "remote", "add", "origin", lock["repository"])
    if subprocess.check_output(
        ["git", "-C", str(hyper), "status", "--porcelain"]
    ).strip():
        raise ValueError("build checkout has local changes")
    run("git", "-C", str(hyper), "fetch", "--depth=1", "origin", revision)
    run("git", "-C", str(hyper), "checkout", "--detach", revision)
    return hyper


def build_image(hyper, profile):
    target = {
        "native": "rpi5-bringup",
        "io-bringup": "rpi5-io-bringup",
        "sd": "rpi5-sd",
    }[profile]
    # Do not inherit local dependency/board overrides into a release build.
    env = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith(("IO_VM_", "RPI5_", "BOARD_", "NATIVE_"))
        and name not in ("MAKEFLAGS", "MAKEOVERRIDES")
    }
    run(
        "make",
        target,
        "ARCH=aarch64",
        "BOARD_IMAGE_REPLACE=--replace",
        cwd=hyper,
        env=env,
    )
    return target


def compress_image(image, dist, profile):
    compressed = dist / f"hyper-rpi5-{profile}.img.xz"
    with image.open("rb") as source, lzma.open(compressed, "wb", preset=6) as output:
        shutil.copyfileobj(source, output)
    # Exercise the stream and check it reconstructs exactly the generated disk.
    with lzma.open(compressed, "rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != sha(image):
        raise ValueError("compressed image round-trip mismatch")
    return digest


def collect_hyper_materials(hyper, dist, revision):
    for name in ("LICENSE", "NOTICE"):
        if (hyper / name).exists():
            shutil.copy2(hyper / name, dist / f"HypeR-{name}")
    run(
        "git",
        "-C",
        str(hyper),
        "archive",
        "--format=tar.gz",
        "-o",
        str(dist / "HypeR-source.tar.gz"),
        revision,
    )
    shutil.copy2(ROOT / "hyper.lock.json", dist / "hyper.lock.json")


def collect_boot_materials(hyper, dist):
    boot = Path(
        subprocess.check_output(
            [sys.executable, "-B", str(hyper / "scripts/fetch-rpi5-boot.py")], text=True
        ).strip()
    )
    for source, name in [
        ("sources.tar.gz", "pi-boot-sources.tar.gz"),
        ("rpi5-boot.lock.json", "pi-boot.lock.json"),
        ("boot-notices.txt", "boot-notices.txt"),
    ]:
        shutil.copy2(boot / source, dist / name)


def collect_io_materials(hyper, dist):
    io_lock = json.loads((hyper / "scripts/io-vm.lock.json").read_text())
    shutil.copy2(hyper / "scripts/io-vm.lock.json", dist / "io-vm.lock.json")
    package = Path(
        subprocess.check_output(
            [
                sys.executable,
                "-B",
                str(hyper / "scripts/fetch-io-vm.py"),
                "--platform",
                "rpi5",
            ],
            text=True,
        ).strip()
    )
    manifest = json.loads((package / "oci-manifest.json").read_text())
    shutil.copy2(package / "oci-manifest.json", dist / "io-vm-manifest.json")
    sys.path.insert(0, str(hyper / "scripts"))
    spec = importlib.util.spec_from_file_location(
        "fetcher", hyper / "scripts/fetch-io-vm.py"
    )
    fetcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fetcher)
    oras = fetcher.ensure_oras()
    repository = io_lock["platforms"]["rpi5"]["reference"].split("@")[0]
    collected = set()
    for layer in manifest["layers"]:
        name = layer["annotations"]["org.opencontainers.image.title"]
        if name not in ("sources.tar.xz", "kernel.config"):
            continue
        output = dist / ("io-vm-" + name)
        run(
            str(oras),
            "blob",
            "fetch",
            "--output",
            str(output),
            repository + "@" + layer["digest"],
        )
        if (
            sha(output) != layer["digest"].removeprefix("sha256:")
            or output.stat().st_size != layer["size"]
        ):
            raise ValueError("I/O source material checksum mismatch")
        collected.add(name)
    if collected != {"sources.tar.xz", "kernel.config"}:
        raise ValueError("I/O package is missing required source materials")


def write_inventory(dist, lock, profile, target, image, digest):
    inventory = {
        "hyper": lock,
        "profile": profile,
        "target": target,
        "image_sha256": digest,
        "image_bytes": image.stat().st_size,
        "files": {
            p.name: {"sha256": sha(p), "bytes": p.stat().st_size}
            for p in sorted(dist.iterdir())
        },
    }
    (dist / "inventory.json").write_text(json.dumps(inventory, indent=2) + "\n")
    shutil.copy2(ROOT / "DISTRIBUTION.md", dist / "DISTRIBUTION.md")
    shutil.copy2(ROOT / "ARTIFACTS.md", dist / "ARTIFACTS.md")
    (dist / "SHA256SUMS").write_text(
        "".join(
            f"{sha(p)}  {p.name}\n"
            for p in sorted(dist.iterdir())
            if p.name != "SHA256SUMS"
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile", choices=["native", "io-bringup", "sd"], default="io-bringup"
    )
    parser.add_argument("--checkout-only", action="store_true")
    args = parser.parse_args()

    lock = json.loads((ROOT / "hyper.lock.json").read_text())
    hyper = checkout_hyper(lock)
    if args.checkout_only:
        return

    dist = ROOT / "dist" / args.profile
    if dist.exists():
        raise ValueError(f"refusing to overwrite {dist}; use a fresh output directory")
    dist.mkdir(parents=True)

    target = build_image(hyper, args.profile)
    image = hyper / "target/board/rpi5-native/disk.img"
    digest = compress_image(image, dist, args.profile)
    collect_hyper_materials(hyper, dist, lock["revision"])
    collect_boot_materials(hyper, dist)
    cache = ROOT / "work/materials-cache"
    materials.collect_rust(hyper, dist / "rust-materials.tar.gz", cache / "crates")
    if args.profile != "native":
        collect_io_materials(hyper, dist)
        libc_pin = json.loads((ROOT / "materials/io-libc.json").read_text())
        materials.collect_libc(
            hyper, dist / "io-libc-materials.tar.gz", cache / "libc", libc_pin
        )
    if args.profile == "sd":
        kernel_pin = json.loads((ROOT / "materials/alpine-kernel.json").read_text())
        materials.collect_alpine(
            hyper, dist / "alpine-materials.tar.gz", cache / "alpine", kernel_pin
        )
    write_inventory(dist, lock, args.profile, target, image, digest)
    print(dist)


if __name__ == "__main__":
    main()
