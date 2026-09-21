<!-- SPDX-FileCopyrightText: 2026 roolrz -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# HypeR Pi 5 images

Downloadable Raspberry Pi 5 SD-card images for [HypeR](https://github.com/roolrz/HypeR).
For HypeR with the Linux I/O VM, SD storage and an Alpine guest, choose
**`hyper-rpi5-sd.img.xz`** from [Releases](https://github.com/roolrz/HypeR-pi5-images/releases).
See [ARTIFACTS.md](ARTIFACTS.md) for the smaller bring-up images and flashing instructions.

## Downloads

- `hyper-rpi5-sd.img.xz`: full system image, approximately 3 GiB after decompression.
- `hyper-rpi5-io-bringup.img.xz`: diskless Linux I/O VM bring-up image.
- `hyper-rpi5-native.img.xz`: HypeR kernel and Native shell image.
- `hyper-rpi5-<profile>-materials.tar.xz`: source archives, input versions and notices.
- `SHA256SUMS`: download checksums.

Images contain a partition table and are written to the **whole SD card**.
Flashing replaces existing partitions and data. The board's EEPROM is not updated.

## Builds and versions

`hyper.lock.json` pins one HypeR commit. I/O VM, official Pi boot inputs and
Alpine versions follow that commit's dependency locks. This repository composes
images using HypeR's build targets; it does not maintain a separate Linux build.
You can also build locally from a HypeR checkout without this repository.

Each update to `main` builds all three profiles and, after successful completion,
creates a Draft Release with compressed images, companion materials and checksums.
Publication is manual. Actions artifacts are available for seven days. Manual
workflow runs can select one profile and optionally create a draft.

For a local Linux build, install HypeR's documented toolchain and image tools,
then run `python3 scripts/build.py --profile sd`. The build uses `work/HypeR`
and writes `dist/sd`; use a fresh output directory for another build.

## Licenses

HypeR-authored code and this repository's build scripts are Apache-2.0.
Images also contain independently licensed components, including Linux and
BusyBox. Each component retains its own license. See
[DISTRIBUTION.md](DISTRIBUTION.md) for component information and the contents
of the accompanying source and notice archives.

## Validation

Native and diskless I/O images run a QEMU GICv2 boot/console smoke test during
assembly. The full SD profile is built but has no automated physical-board test.
Release-specific results belong with the corresponding image version.
