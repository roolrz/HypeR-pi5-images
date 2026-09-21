#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 roolrz
# SPDX-License-Identifier: Apache-2.0
"""Exercise Native console and diskless I/O startup; not a Pi hardware test."""
import argparse
from pathlib import Path
import subprocess
import time

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=['native', 'io-bringup'], required=True)
    parser.add_argument('--kernel', required=True)
    parser.add_argument('--initramfs', required=True)
    parser.add_argument('--log', type=Path, required=True)
    args = parser.parse_args()
    args.log.parent.mkdir(parents=True, exist_ok=True)
    with args.log.open('wb') as log:
        process = subprocess.Popen(['qemu-system-aarch64', '-machine',
            'virt,virtualization=on,gic-version=2', '-cpu', 'cortex-a76',
            '-smp', '4', '-m', '512M', '-display', 'none', '-monitor', 'none',
            '-nic', 'none', '-serial', 'stdio', '-kernel', args.kernel,
            '-initrd', args.initramfs, '-append', 'earlycon=pl011,0x09000000'],
            stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT)
        try:
            def wait(marker):
                deadline = time.monotonic() + 90
                while time.monotonic() < deadline:
                    data = args.log.read_bytes()
                    if process.poll() is not None or b'KERNEL PANIC' in data:
                        raise RuntimeError('guest failed; inspect smoke log')
                    if marker in data:
                        return
                    time.sleep(0.1)
                raise TimeoutError(f'missing {marker!r}; inspect smoke log')
            def send(command):
                process.stdin.write(command + b'\n')
                process.stdin.flush()
            wait(b'hyper-sh$')
            send(b'echo IMAGE-SMOKE-OK')
            wait(b'\nIMAGE-SMOKE-OK\n')
            if args.profile == 'io-bringup':
                send(b'vmm start io-bringup')
                wait(b'vCPU start submitted')
                send(b'vmm console io-bringup')
                wait(b'HypeR I/O: bring-up ready; no devices assigned, storage service disabled')
            print('GICv2 image smoke passed')
        finally:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

if __name__ == '__main__':
    main()
