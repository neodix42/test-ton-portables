"""Check portable stage deadlines and failure propagation in disposable containers."""

import shutil
import subprocess
import unittest

from test_deb import IMAGE, ROOT, write_file


MOCK = r"""#!/bin/bash
set -eu
name=${0##*/}
printf '%s %s\n' "$name" "$*" >> /command.log
case "$name" in
  wget)
    if [[ $FAIL_COMMAND == wget ]]; then exit 4; fi
    ;;
  unzip)
    mkdir -p /usr/local/bin/{smartcont,lib}
    touch /usr/local/bin/smartcont/test.fif /usr/local/bin/lib/test.fif
    ;;
  strings) echo GLIBC_2.35 ;;
  timeout)
    duration=$3
    if [[ $FAIL_COMMAND == java-timeout && $duration == 180s ]] ||
       [[ $FAIL_COMMAND == node-timeout && $duration == 360s ]]; then
      exit 124
    fi
    shift 3
    exec "$@"
    ;;
  java)
    if [[ $FAIL_COMMAND == java ]]; then exit 42; fi
    ;;
  start-node.sh)
    if [[ $FAIL_COMMAND == node ]]; then exit 17; fi
    ;;
esac
"""


@unittest.skipUnless(shutil.which("docker"), "Docker is required for isolated script tests")
class PortableTests(unittest.TestCase):
    def run_script(self, failure=""):
        setup = "set -eu\nmkdir -p /mockbin /app /scripts /usr/share/data /usr/share/ton/smartcont\n"
        setup += write_file("/mockbin/mock", MOCK, executable=True)
        setup += write_file("/app/test-portables.sh", (ROOT / "test-portables.sh").read_text(), executable=True)
        setup += """for command in wget unzip strings lsb_release fift validator-engine validator-engine-console lite-client dht-server ldd timeout java; do
  ln -s /mockbin/mock "/mockbin/$command"
done
ln -s /mockbin/mock /scripts/start-node.sh
touch /usr/share/data/gen-zerostate.fif
export PATH=/mockbin:/usr/bin:/bin ARCH=x86_64
cd /app
set +e
bash /app/test-portables.sh
status=$?
printf '\n__STATUS__=%s\n' "$status"
cat /command.log
"""
        result = subprocess.run(
            ["docker", "run", "--rm", "--user", "0", "--network", "none", "-i",
             "--env", f"FAIL_COMMAND={failure}", "--entrypoint", "/bin/bash", IMAGE, "-s"],
            input=setup, text=True, capture_output=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        status = int(result.stdout.split("__STATUS__=", 1)[1].splitlines()[0])
        return status, result.stdout + result.stderr

    def test_success_has_bounded_download_library_and_node_stages(self):
        status, output = self.run_script()
        self.assertEqual(status, 0, output)
        self.assertIn("wget --timeout=30 --tries=3 --waitretry=2", output)
        self.assertIn("timeout --signal=TERM --kill-after=10s 180s java", output)
        self.assertIn("timeout --signal=TERM --kill-after=30s 360s /scripts/start-node.sh", output)
        self.assertIn("PORTABLE TESTS PASSED", output)

    def test_download_failure_stops_before_binary_tests(self):
        status, output = self.run_script("wget")
        self.assertNotEqual(status, 0, output)
        self.assertNotIn("fift -V", output)
        self.assertNotIn("timeout --signal", output)
        self.assertNotIn("PORTABLE TESTS PASSED", output)

    def test_java_failure_or_timeout_stops_before_genesis(self):
        for failure, expected in [("java", 42), ("java-timeout", 124)]:
            with self.subTest(failure=failure):
                status, output = self.run_script(failure)
                self.assertEqual(status, expected, output)
                self.assertNotIn("start-node.sh", output)
                self.assertNotIn("PORTABLE TESTS PASSED", output)

    def test_genesis_failure_or_timeout_fails_the_suite(self):
        for failure, expected in [("node", 17), ("node-timeout", 124)]:
            with self.subTest(failure=failure):
                status, output = self.run_script(failure)
                self.assertEqual(status, expected, output)
                self.assertIn("Portable genesis tests FAILED", output)
                self.assertNotIn("PORTABLE TESTS PASSED", output)


if __name__ == "__main__":
    unittest.main()
