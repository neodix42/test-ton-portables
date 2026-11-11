"""Run with: python3 -m unittest discover -s tests -p test_deb.py -v.

Requires Docker and an Ubuntu image with Bash. Set TEST_DOCKER_IMAGE to an existing
image to avoid a pull, for example TEST_DOCKER_IMAGE=ubuntu:24.04. Every scenario
runs in a disposable container with networking disabled and no host mounts.
"""

import os
from pathlib import Path
import shlex
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
IMAGE = os.environ.get("TEST_DOCKER_IMAGE", "ubuntu:24.04")


MOCK = r"""#!/bin/bash
set -eu
name=${0##*/}
printf '%s\t%s\n' "$name" "$*" >> "$COMMAND_LOG"
case "$name" in
  dpkg) printf '%s\n' "$TEST_ARCH" ;;
  apt-get)
    operation=${!#}
    if [[ $operation == update && $FAIL_COMMAND == apt-update ]] ||
       [[ $operation == ton && $FAIL_COMMAND == apt-install ]]; then
      exit "$FAIL_STATUS"
    fi
    if [[ $operation == ton ]]; then
      printf 'installed contract\n' > /usr/share/ton/smartcont/wallet-v3-code.fif
    fi
    ;;
  install|rm|cp) "/usr/bin/$name" "$@" ;;
  java|fift|validator-engine|validator-engine-console|lite-client|dht-server|ldd)
    if [[ $FAIL_COMMAND == "$name" ]]; then exit "$FAIL_STATUS"; fi
    ;;
  start-node.sh)
    printf 'node-libraries\t%s %s\n' "$TONLIBJSON_PATH" "$LIBEMULATOR_PATH" >> "$COMMAND_LOG"
    if [[ $FAIL_COMMAND == node ]]; then exit "$FAIL_STATUS"; fi
    ;;
  test-portables.sh) exit "$PORTABLE_STATUS" ;;
  test-deb.sh) exit "$DEB_STATUS" ;;
esac
"""


def write_file(path, content, executable=False):
    """Create a file through stdin inside the container, never on the host."""
    delimiter = "__TON_TEST_FILE_END__"
    assert delimiter not in content
    script = f"cat > {shlex.quote(path)} <<'{delimiter}'\n{content}\n{delimiter}\n"
    if executable:
        script += f"chmod 755 {shlex.quote(path)}\n"
    return script


class DebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("docker"):
            raise unittest.SkipTest("Docker is required for isolated script tests")

    def run_script(self, *, distro="ubuntu", suite="noble", arch="amd64",
                   ubuntu_codename=None, fail="", status=23, entry=False,
                   portable_status=0, deb_status=0):
        os_release = f"ID={shlex.quote(distro)}\nVERSION_CODENAME={shlex.quote(suite)}\n"
        if ubuntu_codename is not None:
            os_release += f"UBUNTU_CODENAME={shlex.quote(ubuntu_codename)}\n"
        # Local Git configurations may check scripts out with CRLF; read_text
        # gives the LF form stored in Git and used by Linux Actions checkouts.
        setup = "set -eu\nmkdir -p /mockbin /app /scripts /etc/apt/sources.list.d /usr/share/data /usr/share/ton/smartcont /var/ton-work /usr/local/bin\n"
        setup += write_file("/etc/os-release", os_release)
        setup += write_file("/mockbin/mock", MOCK, executable=True)
        setup += write_file("/app/ton-foundation-ppa.asc", (ROOT / "keys/ton-foundation-ppa.asc").read_text())
        setup += write_file("/app/test-deb.sh", (ROOT / "test-deb.sh").read_text(), executable=True)
        setup += write_file("/app/entry.sh", (ROOT / "entry.sh").read_text(), executable=True)
        setup += """for command in dpkg apt-get install rm cp fift validator-engine validator-engine-console lite-client dht-server ldd java; do
  ln -s /mockbin/mock "/mockbin/$command"
done
ln -s /mockbin/mock /scripts/start-node.sh
ln -s /mockbin/mock /app/test-portables.sh
touch /usr/local/bin/old-portable /usr/share/ton/smartcont/old-smartcont /var/ton-work/old-state
touch /usr/share/data/gen-zerostate.fif
"""
        if entry:
            setup += "mv /app/test-deb.sh /app/test-deb-real.sh\nln -s /mockbin/mock /app/test-deb.sh\n"
        environment = {
            "PATH": "/mockbin:/usr/bin:/bin",
            "COMMAND_LOG": "/command.log",
            "TEST_ARCH": arch,
            "FAIL_COMMAND": fail,
            "FAIL_STATUS": str(status),
            "PORTABLE_STATUS": str(portable_status),
            "DEB_STATUS": str(deb_status),
        }
        for name, value in environment.items():
            setup += f"export {name}={shlex.quote(value)}\n"
        target = "/app/entry.sh" if entry else "/app/test-deb.sh"
        setup += f"set +e\n/bin/bash {target}\nresult=$?\n"
        setup += """printf '\n__TON_RESULT__=%s\n' "$result"
printf '__TON_LOG_BEGIN__\n'
if [[ -f /command.log ]]; then cat /command.log; fi
printf '__TON_LOG_END__\n'
printf '__TON_SOURCE_BEGIN__\n'
if [[ -f /etc/apt/sources.list.d/ton-foundation-ppa.list ]]; then cat /etc/apt/sources.list.d/ton-foundation-ppa.list; fi
printf '__TON_SOURCE_END__\n'
for marker in /usr/local/bin/old-portable /usr/share/ton/smartcont/old-smartcont /var/ton-work/old-state; do
  if [[ -f $marker ]]; then printf '__TON_RETAINED__=%s\n' "$marker"; fi
done
if [[ -f /usr/share/ton/smartcont/wallet-v3-code.fif ]]; then
  printf '__TON_INSTALLED_CONTRACT_RETAINED__\n'
fi
exit 0
"""
        run = subprocess.run(
            ["docker", "run", "--rm", "--user", "0", "--network", "none", "-i",
             "--entrypoint", "/bin/bash", IMAGE, "-s"],
            input=setup, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        output = run.stdout + run.stderr
        self.assertIn("__TON_RESULT__=", run.stdout, output)
        result = int(run.stdout.split("__TON_RESULT__=", 1)[1].splitlines()[0])
        log = run.stdout.split("__TON_LOG_BEGIN__\n", 1)[1].split("__TON_LOG_END__", 1)[0].splitlines()
        source = run.stdout.split("__TON_SOURCE_BEGIN__\n", 1)[1].split("__TON_SOURCE_END__", 1)[0]
        commands = [line.split("\t", 1)[0] for line in log]
        retained = sum(line.startswith("__TON_RETAINED__=") for line in run.stdout.splitlines())
        return result, commands, log, source, retained, output

    def test_unsupported_platform_skips_before_mutation(self):
        cases = [
            dict(suite="plucky"), dict(suite="resolute"),
            dict(distro="debian", suite="bookworm"),
            dict(distro="unknown", suite="noble"),
            dict(distro="linuxmint", suite="wilma"),
            dict(arch="armhf"), dict(arch="i386"),
        ]
        for case in cases:
            with self.subTest(**case):
                code, commands, _, source, retained, output = self.run_script(**case)
                self.assertEqual(code, 0, output)
                self.assertIn("DEB TESTS SKIPPED", output)
                self.assertTrue(set(commands).issubset({"dpkg"}), commands)
                self.assertEqual(source, "")
                self.assertEqual(retained, 3, output)

    def test_published_suites_and_mint_use_native_packages(self):
        cases = [
            dict(suite="jammy", arch="amd64"),
            dict(suite="jammy", arch="arm64"),
            dict(suite="noble", arch="amd64"),
            dict(suite="noble", arch="arm64"),
            dict(distro="linuxmint", suite="victoria", ubuntu_codename="jammy"),
            dict(distro="linuxmint", suite="wilma", ubuntu_codename="noble"),
        ]
        for case in cases:
            with self.subTest(**case):
                code, commands, log, source, retained, output = self.run_script(**case)
                self.assertEqual(code, 0, output)
                self.assertIn("DEB TESTS PASSED", output)
                apt_calls = [i for i, command in enumerate(commands) if command == "apt-get"]
                self.assertEqual(len(apt_calls), 2, log)
                self.assertLess(apt_calls[0], commands.index("rm"), log)
                self.assertLess(commands.index("rm"), apt_calls[1], log)
                self.assertLess(apt_calls[1], commands.index("fift"), log)
                self.assertIn("java", commands)
                self.assertIn("start-node.sh", commands)
                self.assertIn("node-libraries\t/usr/lib/libtonlibjson.so.0.5 /usr/lib/libemulator.so", log)
                suite = case.get("ubuntu_codename", case.get("suite", "noble"))
                self.assertIn(f" {suite} main", source)
                self.assertIn(f"arch={case.get('arch', 'amd64')}", source)
                self.assertIn("signed-by=/etc/apt/keyrings/ton-foundation-ppa.asc", source)
                self.assertEqual(retained, 0, output)
                self.assertIn("__TON_INSTALLED_CONTRACT_RETAINED__", output)

    def test_apt_failures_stop_before_binary_tests(self):
        for failure, expected_apt_calls in [("apt-update", 1), ("apt-install", 2)]:
            with self.subTest(failure=failure):
                code, commands, _, _, retained, output = self.run_script(fail=failure)
                self.assertEqual(code, 23, output)
                self.assertEqual(commands.count("apt-get"), expected_apt_calls, commands)
                if failure == "apt-update":
                    self.assertNotIn("rm", commands)
                    self.assertEqual(retained, 3, output)
                else:
                    self.assertIn("rm", commands)
                    self.assertEqual(retained, 0, output)
                self.assertNotIn("fift", commands)
                self.assertNotIn("java", commands)
                self.assertNotIn("DEB TESTS PASSED", output)

    def test_binary_and_library_failures_stop_the_test(self):
        for failure in ["fift", "validator-engine", "ldd", "java", "node"]:
            with self.subTest(failure=failure):
                code, commands, _, _, _, output = self.run_script(fail=failure)
                self.assertNotEqual(code, 0, output)
                if failure != "fift":
                    self.assertEqual(code, 23, output)
                self.assertNotIn("DEB TESTS PASSED", output)
                if failure != "node":
                    self.assertNotIn("start-node.sh", commands)

    def test_entry_stops_after_portable_failure(self):
        code, commands, _, _, _, output = self.run_script(entry=True, portable_status=17)
        self.assertNotEqual(code, 0, output)
        self.assertEqual(commands, ["test-portables.sh"])
        self.assertIn("PORTABLE TESTS FAILED", output)

    def test_entry_propagates_deb_exit_status(self):
        for distro in ["ubuntu", "linuxmint"]:
            for deb_status in [0, 23]:
                with self.subTest(distro=distro, deb_status=deb_status):
                    code, commands, _, _, _, output = self.run_script(
                        entry=True, distro=distro, deb_status=deb_status,
                    )
                    self.assertEqual(code, deb_status, output)
                    self.assertEqual(commands, ["test-portables.sh", "test-deb.sh"])

    def test_entry_skips_deb_on_other_distributions(self):
        for distro in ["debian", "fedora", "arch"]:
            with self.subTest(distro=distro):
                code, commands, _, _, _, output = self.run_script(entry=True, distro=distro)
                self.assertEqual(code, 0, output)
                self.assertEqual(commands, ["test-portables.sh"])
                self.assertIn("DEB TESTS SKIPPED", output)

    def test_start_node_replaces_portable_libraries_and_stops_on_missing_files(self):
        for mode in ["portable", "native", "missing"]:
            with self.subTest(mode=mode):
                setup = "set -eu\nmkdir -p /scripts /usr/share/data /usr/local/bin /native\n"
                setup += write_file("/scripts/start-node.sh", (ROOT / "genesis/scripts/start-node.sh").read_text(), executable=True)
                setup += write_file("/usr/local/bin/libtonlibjson.so", "portable-tonlib")
                setup += write_file("/usr/local/bin/libemulator.so", "portable-emulator")
                setup += write_file("/native/libtonlibjson.so.0.5", "native-tonlib")
                setup += write_file("/native/libemulator.so", "native-emulator")
                # The portable suite leaves these files behind before DEB tests.
                setup += write_file("/usr/share/data/libtonlibjson.so", "stale-tonlib")
                setup += write_file("/usr/share/data/libemulator.so", "stale-emulator")
                expected = "native" if mode == "native" else "portable"
                genesis = f"""#!/bin/bash
set -eu
[[ $(cat /usr/share/data/libtonlibjson.so) == {expected}-tonlib ]]
[[ $(cat /usr/share/data/libemulator.so) == {expected}-emulator ]]
echo GENESIS_REACHED
"""
                setup += write_file("/scripts/start-genesis.sh", genesis, executable=True)
                setup += "export GENESIS=true\n"
                if mode != "portable":
                    tonlib = "/native/libtonlibjson.so.0.5" if mode == "native" else "/native/missing.so"
                    setup += f"export TONLIBJSON_PATH={tonlib} LIBEMULATOR_PATH=/native/libemulator.so\n"
                setup += "/bin/bash /scripts/start-node.sh\n"
                result = subprocess.run(
                    ["docker", "run", "--rm", "--user", "0", "--network", "none", "-i",
                     "--entrypoint", "/bin/bash", IMAGE, "-s"],
                    input=setup, capture_output=True, text=True, timeout=30,
                )
                if mode == "missing":
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertNotIn("GENESIS_REACHED", result.stdout)
                else:
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("GENESIS_REACHED", result.stdout)


if __name__ == "__main__":
    unittest.main()
