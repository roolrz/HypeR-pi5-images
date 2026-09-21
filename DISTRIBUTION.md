<!-- SPDX-FileCopyrightText: 2026 roolrz -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Image components and source materials

The disk image combines independently licensed components. HypeR-authored
kernel, application and SDK code retains Apache-2.0; Linux, BusyBox, libraries,
firmware inputs and Alpine packages retain their own licenses. This repository's
Apache-2.0 license covers its build scripts, not every file in the disk image.

## Components

| Component | License information | Accompanying materials |
| --- | --- | --- |
| Image build scripts | Apache-2.0 | This repository's LICENSE and release commit |
| HypeR-authored kernel, applications and SDK | Apache-2.0 | HypeR-LICENSE, HypeR-NOTICE when present, HypeR-source.tar.gz |
| Rust standard library, runtime and linked crates | Respective upstream licenses | Dependency versions and build recipes in the HypeR source archive; a consolidated dependency notice archive is not currently generated |
| I/O VM Linux and bridge modules | Linux license terms and per-file exceptions; bridge modules GPL-2.0-only | io-vm-sources.tar.xz, io-vm-kernel.config, io-vm.lock.json and io-vm-manifest.json |
| I/O VM BusyBox and services | BusyBox GPL terms; project-authored services Apache-2.0; linked libraries retain their own licenses | Appliance sources and build configuration in io-vm-sources.tar.xz; the image assembler does not separately inventory static libc inputs |
| Pi device trees and overlays | Upstream per-file licenses | pi-boot-sources.tar.gz, pi-boot.lock.json and boot-notices.txt |
| Alpine kernel and rootfs (SD profile) | Per-package licenses | Input versions and download checksums in HypeR sources; Alpine package source archives are not included in the current materials bundle |
| Board EEPROM and its bundled firmware | Vendor terms | Not included or updated by these images |

## Companion archive

Each `hyper-rpi5-<profile>-materials.tar.xz` accompanies one image and contains:

- `inventory.json`: HypeR revision, build profile, image size and SHA-256, and
  hashes of the recorded inputs.
- `hyper.lock.json` and the exact HypeR source archive.
- Official Pi boot-input sources, lock and notices.
- For I/O profiles, the pinned appliance manifest, source layer and kernel configuration.
- Component documentation and checksums.

The inventory identifies the shipped artifacts. It is not a license certificate
or a physical-hardware test report. The table above describes what the build
actually supplies, including material it does not yet collect.

## Source provenance

The build fetches a fixed HypeR commit and follows its dependency locks. I/O
source layers are checked against OCI size and SHA-256 descriptors. Official Pi
boot inputs are validated by HypeR's download tooling. Source archives retain
the upstream license files they contain; they are not relicensed by this repository.

The image build and bundle scripts are available in `scripts/`. Release assets
are assembled from the same Actions outputs without rebuilding the images.
