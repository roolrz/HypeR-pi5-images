# SPDX-FileCopyrightText: 2026 roolrz
# SPDX-License-Identifier: Apache-2.0

import importlib.util
import json
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("smoke", ROOT / "scripts/smoke.py")
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


class SmokeTests(unittest.TestCase):
    def test_io_smoke_starts_and_attaches_the_configured_vm(self):
        process = Mock()
        process.poll.return_value = 0
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "vms.json"
            config.write_text(
                json.dumps(
                    {
                        "format": "hyper.vm-config",
                        "virtual-machines": [{"name": "Storage_IO.1"}],
                    }
                )
            )
            arguments = [
                "smoke.py",
                "--profile",
                "io-bringup",
                "--kernel",
                "hyper.img",
                "--initramfs",
                "bootstrap.cpio",
                "--vm-config",
                str(config),
                "--log",
                str(root / "smoke.log"),
            ]
            with (
                patch.object(sys, "argv", arguments),
                patch.object(smoke.subprocess, "Popen", return_value=process),
                patch.object(smoke, "wait_for_output"),
            ):
                smoke.main()
            self.assertEqual(
                [call.args[0] for call in process.stdin.write.call_args_list],
                [
                    b"echo IMAGE-SMOKE-OK\n",
                    b"vmm start Storage_IO.1\n",
                    b"vmm console Storage_IO.1\n",
                ],
            )
            process.wait.assert_called_once_with(timeout=5)

    def test_vm_name_follows_generated_configuration(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "vms.json"
            for name in ("io", "Storage_IO.1"):
                with self.subTest(name=name):
                    path.write_text(
                        json.dumps(
                            {
                                "format": "hyper.vm-config",
                                "virtual-machines": [{"name": name}],
                            }
                        )
                    )
                    self.assertEqual(smoke.bringup_vm_name(path), name.encode())

    def test_missing_ambiguous_or_unsafe_names_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "vms.json"
            for machines in (
                [],
                [{"name": "io"}, {"name": "other"}],
                [{}],
                [{"name": "io\necho success"}],
                [{"name": "-io"}],
            ):
                with self.subTest(machines=machines):
                    path.write_text(
                        json.dumps(
                            {
                                "format": "hyper.vm-config",
                                "virtual-machines": machines,
                            }
                        )
                    )
                    with self.assertRaises(ValueError):
                        smoke.bringup_vm_name(path)

    def test_command_failure_is_reported_without_waiting_for_timeout(self):
        process = Mock()
        process.poll.return_value = None
        with tempfile.TemporaryDirectory() as temporary:
            log = Path(temporary) / "smoke.log"
            log.write_bytes(
                b"vmm: VM 'io-bringup' does not exist; use 'vmm list'\n"
                b"sh: command failed\n"
            )
            with patch.object(smoke.time, "sleep") as sleep:
                with self.assertRaisesRegex(RuntimeError, "does not exist"):
                    smoke.wait_for_output(process, log, b"vCPU start submitted")
                sleep.assert_not_called()

    def test_expected_output_completes_with_running_guest(self):
        process = Mock()
        process.poll.return_value = None
        with tempfile.TemporaryDirectory() as temporary:
            log = Path(temporary) / "smoke.log"
            log.write_bytes(b"echo IMAGE-SMOKE-OK\nIMAGE-SMOKE-OK\n")
            smoke.wait_for_output(process, log, b"\nIMAGE-SMOKE-OK\n")


if __name__ == "__main__":
    unittest.main()
