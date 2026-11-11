"""Exercise node lifecycle handling without running the destructive genesis setup."""

import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
import unittest


REPOSITORY = Path(__file__).resolve().parents[1]
LIVE_CHILD_HELPER = """
start_live_child() {
  bash -c 'echo "$$" >> "$PID_FILE"; : > "$READY_FILE.$$"; exec sleep 60' &
  local child_pid=$!
  printf -v "$1" '%s' "$child_pid"
  while [ ! -e "$READY_FILE.$child_pid" ]; do sleep 0.01; done
}
"""


@unittest.skipUnless(shutil.which("bash"), "Bash is required")
class GenesisLifecycleTests(unittest.TestCase):
    def setUp(self):
        source = (REPOSITORY / "genesis/scripts/start-genesis.sh").read_text()
        marker = "INTERNAL_IP=127.0.0.1"
        self.assertEqual(source.count(marker), 1, "Genesis helper boundary changed")
        self.helpers = source.partition(marker)[0]
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.pid_file = Path(self.directory.name) / "pids"
        self.ready_file = Path(self.directory.name) / "ready"
        self.environment = {
            **os.environ,
            "PID_FILE": str(self.pid_file),
            "READY_FILE": str(self.ready_file),
        }
        self.addCleanup(self.kill_remaining_children)

    def child_pids(self):
        if not self.pid_file.exists():
            return []
        return [int(pid) for pid in self.pid_file.read_text().split()]

    def kill_remaining_children(self):
        for pid in self.child_pids():
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def assert_children_stopped(self):
        for pid in self.child_pids():
            with self.assertRaises(ProcessLookupError, msg=f"Child {pid} survived cleanup"):
                os.kill(pid, 0)

    def launch(self, body):
        # Only source definitions and traps; never execute the system setup below them.
        script = "ulimit -c 0\n" + self.helpers + LIVE_CHILD_HELPER + body
        process = subprocess.Popen(
            ["bash", "-c", script],
            env=self.environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )

        def stop_process_group():
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate(timeout=5)

        self.addCleanup(stop_process_group)
        return process

    def finish(self, process, expected_status):
        stdout, stderr = process.communicate(timeout=15)
        self.assertEqual(process.returncode, expected_status, stdout + stderr)
        self.assert_children_stopped()
        return stdout + stderr

    def run_case(self, body, expected_status):
        return self.finish(self.launch(body), expected_status)

    def test_requested_termination_succeeds(self):
        self.run_case(
            """
start_live_child VALIDATOR_RUN
stop_background VALIDATOR_RUN validator
""",
            0,
        )

    def test_prior_clean_exit_is_failure(self):
        output = self.run_case(
            """
bash -c 'exit 0' &
VALIDATOR_RUN=$!
echo "$VALIDATOR_RUN" >> "$PID_FILE"
wait "$VALIDATOR_RUN" || true
stop_background VALIDATOR_RUN validator
""",
            1,
        )
        self.assertIn("exited unexpectedly (status 0)", output)

    def test_prior_crash_status_is_preserved(self):
        self.run_case(
            """
bash -c 'exit 134' &
VALIDATOR_RUN=$!
echo "$VALIDATOR_RUN" >> "$PID_FILE"
wait "$VALIDATOR_RUN" || true
stop_background VALIDATOR_RUN validator
""",
            134,
        )

    def test_sigabrt_is_failure(self):
        self.run_case(
            """
bash -c 'kill -ABRT $$' &
VALIDATOR_RUN=$!
echo "$VALIDATOR_RUN" >> "$PID_FILE"
wait "$VALIDATOR_RUN" || true
stop_background VALIDATOR_RUN validator
""",
            134,
        )

    def test_crash_during_requested_shutdown_is_failure(self):
        self.run_case(
            """
bash -c 'trap "exit 134" TERM; echo ready > "$READY_FILE"; while :; do sleep 0.05; done' &
VALIDATOR_RUN=$!
echo "$VALIDATOR_RUN" >> "$PID_FILE"
while [ ! -e "$READY_FILE" ]; do sleep 0.01; done
stop_background VALIDATOR_RUN validator
""",
            134,
        )

    def test_cleanup_preserves_original_failure(self):
        self.run_case(
            """
bash -c 'exit 134' &
VALIDATOR_RUN=$!
echo "$VALIDATOR_RUN" >> "$PID_FILE"
start_live_child DHT_SERVER_RUN
wait "$VALIDATOR_RUN" || true
exit 7
""",
            7,
        )

    def test_cleanup_detects_crash_after_nominal_success(self):
        self.run_case(
            """
bash -c 'exit 134' &
VALIDATOR_RUN=$!
echo "$VALIDATOR_RUN" >> "$PID_FILE"
wait "$VALIDATOR_RUN" || true
exit 0
""",
            134,
        )

    def test_exit_cleans_up_all_node_processes(self):
        self.run_case(
            """
for child_var in PRELIMINARY_DHT_SERVER_RUN PRELIMINARY_VALIDATOR_RUN DHT_SERVER_RUN VALIDATOR_RUN; do
  start_live_child "$child_var"
done
exit 0
""",
            0,
        )
        self.assertEqual(len(self.child_pids()), 4)

    def test_term_interrupt_cleans_up_nodes_and_test_wait(self):
        process = self.launch(
            """
for child_var in PRELIMINARY_DHT_SERVER_RUN PRELIMINARY_VALIDATOR_RUN DHT_SERVER_RUN VALIDATOR_RUN TEST_WAIT_RUN; do
  start_live_child "$child_var"
done
wait "$TEST_WAIT_RUN"
"""
        )
        deadline = time.monotonic() + 5
        while len(self.child_pids()) != 5:
            self.assertIsNone(process.poll(), "Harness exited before launching children")
            self.assertLess(time.monotonic(), deadline, "Children did not launch in time")
            time.sleep(0.01)
        process.terminate()
        self.finish(process, 143)


if __name__ == "__main__":
    unittest.main()
