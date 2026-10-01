#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 roolrz
# SPDX-License-Identifier: Apache-2.0
"""Exercise Native console and diskless I/O startup; not a Pi hardware test."""

import argparse
import json
import re
import subprocess
import time
from pathlib import Path


def bringup_vm_name(config_path):
    config = json.loads(config_path.read_text())
    machines = config.get("virtual-machines", [])
    if config.get("format") != "hyper.vm-config" or len(machines) != 1:
        raise ValueError("bring-up requires exactly one configured VM")
    name = machines[0].get("name")
    if not isinstance(name, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.-]{0,31}", name
    ):
        raise ValueError("invalid bring-up VM name")
    return name.encode("ascii")


def wait_for_output(process, log_path, marker):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        data = log_path.read_bytes()
        failures = (
            b"KERNEL PANIC",
            b"HypeR init: bootstrap failed",
            b"HypeR vm-manager: fleet configuration rejected",
            b"vmm:",
            b"sh: command failed",
        )
        if process.poll() is not None or any(failure in data for failure in failures):
            raise RuntimeError(
                f"guest failed; inspect {log_path}:\n{data[-4096:].decode(errors='replace')}"
            )
        if marker in data:
            return
        time.sleep(0.1)
    raise TimeoutError(f"missing {marker!r}; inspect smoke log")


def send_command(process, command):
    process.stdin.write(command + b"\n")
    process.stdin.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=["native", "io-bringup"], required=True)
    parser.add_argument("--kernel", required=True)
    parser.add_argument("--initramfs", required=True)
    parser.add_argument(
        "--vm-config", type=Path, help="generated bringup/vms.json for io-bringup"
    )
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args()
    if args.profile == "io-bringup":
        if args.vm_config is None:
            parser.error("--vm-config is required for io-bringup")
        vm_name = bringup_vm_name(args.vm_config)
    args.log.parent.mkdir(parents=True, exist_ok=True)
    with args.log.open("wb") as log:
        process = subprocess.Popen(
            [
                "qemu-system-aarch64",
                "-machine",
                "virt,virtualization=on,gic-version=2",
                "-cpu",
                "cortex-a76",
                "-smp",
                "4",
                "-m",
                "512M",
                "-display",
                "none",
                "-monitor",
                "none",
                "-nic",
                "none",
                "-serial",
                "stdio",
                "-kernel",
                args.kernel,
                "-initrd",
                args.initramfs,
                "-append",
                "earlycon=pl011,0x09000000",
            ],
            stdin=subprocess.PIPE,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            wait_for_output(process, args.log, b"hyper-sh$")
            send_command(process, b"echo IMAGE-SMOKE-OK")
            wait_for_output(process, args.log, b"\nIMAGE-SMOKE-OK\n")
            if args.profile == "io-bringup":
                wait_for_output(process, args.log, b"HypeR init: VM fleet configured")
                send_command(process, b"vmm start " + vm_name)
                wait_for_output(process, args.log, b"vCPU start submitted")
                send_command(process, b"vmm console " + vm_name)
                wait_for_output(
                    process,
                    args.log,
                    b"HypeR I/O: bring-up ready; no devices assigned, storage service disabled",
                )
            print("GICv2 image smoke passed")
        finally:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    main()
