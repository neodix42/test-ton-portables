"""Optional regression test against real TON binaries, using only temporary data.

TON_BUILD_DIR=/path/to/ton/build python3 -m unittest discover -s tests -p test_fullnode_rotation.py -v
TON_VALIDATOR_ENGINE can override the validator executable for before/after checks.
"""

import base64
import json
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import unittest


BUILD = os.environ.get("TON_BUILD_DIR")


@unittest.skipUnless(BUILD, "Set TON_BUILD_DIR to run real TON rotation tests")
class FullNodeRotationTests(unittest.TestCase):
    def setUp(self):
        build = Path(BUILD).resolve()
        self.engine = Path(os.environ.get("TON_VALIDATOR_ENGINE", build / "validator-engine/validator-engine"))
        self.console = build / "validator-engine-console/validator-engine-console"
        self.keygen = build / "utils/generate-random-id"
        for executable in [self.engine, self.console, self.keygen]:
            self.assertTrue(executable.is_file(), f"Missing TON executable: {executable}")
        self.directory = tempfile.TemporaryDirectory(prefix="ton-rotation-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.db = self.root / "db"
        self.log = self.root / "validator.log"
        self.process = None

    def run_command(self, arguments, timeout=15):
        result = subprocess.run(
            [str(arg) for arg in arguments], cwd=self.root,
            capture_output=True, text=True, timeout=timeout,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout + result.stderr

    def free_port(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            return listener.getsockname()[1]

    def console_command(self, command):
        return self.run_command([
            self.console, "-k", self.root / "client", "-p", self.root / "server.pub",
            "-v", "0", "-a", f"127.0.0.1:{self.control_port}", "-t", "3", "-rc", command,
        ], timeout=5)

    def read_log(self):
        return self.log.read_text(errors="replace")

    def stop_engine(self):
        if self.process and self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGTERM)
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait(timeout=5)

    def check_rotation(self, acceptance):
        # No live-chain peers or state are needed to exercise ADNL identity rotation.
        zero_hash = base64.b64encode(bytes([1]) * 32).decode()
        block = {
            "workchain": -1, "shard": -9223372036854775808, "seqno": 0,
            "root_hash": zero_hash, "file_hash": zero_hash,
        }
        global_config = self.root / "global.json"
        global_config.write_text(json.dumps({
            "@type": "config.global",
            "dht": {"@type": "dht.config.global", "k": 3, "a": 3,
                    "static_nodes": {"@type": "dht.nodes", "nodes": []}},
            "validator": {"@type": "validator.config.global", "zero_state": block},
        }))
        engine_arguments = [
            self.engine, "-C", global_config, "--db", self.db,
            "--ip", f"127.0.0.1:{self.free_port()}", "-v", "1",
        ]
        # The first invocation creates keys/configuration and exits normally.
        self.run_command(engine_arguments)
        config_path = self.db / "config.json"
        config = json.loads(config_path.read_text())
        key_ids = {}
        for name in ["server", "client"]:
            output = self.run_command([self.keygen, "-m", "keys", "-n", self.root / name])
            key_hex, key_base64 = output.strip().split()[-2:]
            key_ids[name] = key_base64
            if name == "server":
                shutil.copyfile(self.root / name, self.db / "keyring" / key_hex)
        self.control_port = self.free_port()
        config["control"] = [{
            "id": key_ids["server"], "port": self.control_port,
            "allowed": [{"id": key_ids["client"], "permissions": 15}],
        }]
        config_path.write_text(json.dumps(config))
        if acceptance is not None:
            engine_arguments += ["--accept-certs-from", acceptance]

        def disable_core_dumps():
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

        with self.log.open("w") as log:
            self.process = subprocess.Popen(
                [str(arg) for arg in engine_arguments], cwd=self.root,
                stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True, preexec_fn=disable_core_dumps,
            )
        self.addCleanup(self.stop_engine)
        deadline = time.monotonic() + 15
        while True:
            self.assertIsNone(self.process.poll(), self.read_log())
            try:
                with socket.create_connection(("127.0.0.1", self.control_port), timeout=0.1):
                    break
            except OSError:
                self.assertLess(time.monotonic(), deadline, self.read_log())
                time.sleep(0.05)

        # Rotate twice: both the original and replacement identities must have
        # matching subscription/unsubscription behavior. Leave certificate flags
        # at their defaults for the configuration that crashed in Actions.
        for _ in range(2):
            output = self.console_command("newkey")
            key = re.search(r"created new key\s+([0-9a-fA-F]{64})", output)
            self.assertIsNotNone(key, output)
            key_hex = key.group(1)
            self.assertIn("success", self.console_command(f"addadnl {key_hex} 0"))
            self.assertIn("success", self.console_command(f"changefullnodeaddr {key_hex}"))
            # A subsequent command proves the engine can still serve requests
            # after processing the asynchronous subscription changes.
            time.sleep(0.2)
            self.assertIsNone(self.process.poll(), self.read_log())
            self.assertIn("created new key", self.console_command("newkey"))
        self.assertNotIn("cannot unsubscribe", self.read_log())
        self.stop_engine()
        self.assertIn(self.process.returncode, [0, -signal.SIGTERM], self.read_log())

    def test_rotation_without_certificate_subscription(self):
        self.check_rotation(None)

    def test_rotation_accepting_any_validator(self):
        self.check_rotation("*")

    def test_rotation_accepting_configured_sender(self):
        self.check_rotation("11" * 32)


if __name__ == "__main__":
    unittest.main()
