# Test TON artifacts
Set of Github actions used to test TON portable binaries, as well as deb packages from PPA launchpad repository against various Linux platforms.

Each Linux workflow runs two independent job matrices, so a portable failure cannot prevent a DEB test from running:

- **Portable binaries** downloads the [release bundle](https://github.com/neodix42/ton/releases/latest), checks its binaries and libraries, then starts a fresh standalone blockchain with those binaries.
- **DEB packages** installs `ton` from the TON Foundation PPA, checks the installed binaries and libraries, then starts its own fresh blockchain. It downloads its own [library test runner](https://github.com/neodix42/test-ton-libs/releases/latest/download/test-ton-libs.jar) and does not depend on portable artifacts.

A blockchain test succeeds only after generating 30 blocks and verifying that its node processes did not crash. Missing required tools, including `create-state`, remain real failures. No portable fallback or genesis skip is used for DEB packages.

Every Linux job has a 15-minute limit. Downloads use a 30-second network timeout with up to three attempts; library tests have a 180-second limit and blockchain tests a 360-second limit. Timed-out stages fail their suite.

DEB jobs currently cover Ubuntu 22.04 (`jammy`) and 24.04 (`noble`) on `amd64` and `arm64`, plus Mint 21 on `amd64`. Portable jobs retain the full distribution matrices, including Ubuntu 25/26 and Debian. Extend the DEB matrix and the allowlist in `test-deb.sh` only after the PPA publishes `ton` for that release and architecture.

The PPA is configured directly with HTTPS and a repository-specific `Signed-By` keyring, without `apt-key`, keyserver access, or a Launchpad API request during tests. The bundled public key is [keys/ton-foundation-ppa.asc](keys/ton-foundation-ppa.asc), with fingerprint `81D5BBE5E77AB2FAC1886F78F6A649124520E5F3`, verified against the [PPA metadata](https://api.launchpad.net/1.0/~ton-foundation/+archive/ubuntu/ppa). When updating the key, verify its full fingerprint against that metadata before replacing it. Repository download errors retry up to three times; setup or test failures stop the DEB test immediately.

# Test TON compilation
```bash
docker build -f dockerfile-debian-12-compile -t ton-build .
docker run ton-build
```

## Test the shell harness

Run the regression tests with Python 3 and Docker:

```bash
docker pull ubuntu:24.04
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

Repository setup tests run with mocked commands in disposable containers with networking disabled and no host mounts. Node lifecycle tests use isolated child processes. Neither test suite starts a TON blockchain or modifies host system directories. Set `TEST_DOCKER_IMAGE` to use a different local Ubuntu image.

To check full-node identity rotation against a real TON build (including the default certificate settings that exposed the validator crash):

```bash
PYTHONDONTWRITEBYTECODE=1 TON_BUILD_DIR=/path/to/ton/build \
  python3 -m unittest discover -s tests -p test_fullnode_rotation.py -v
```

This optional integration test uses temporary databases, local ports, and no live-chain peers. It rotates the full-node ADNL identity twice with certificate acceptance disabled, enabled for any validator, and enabled for one sender. Set `TON_VALIDATOR_ENGINE` to compare a different validator executable against the same helper binaries. Without `TON_BUILD_DIR`, these integration tests are skipped.

## Run a container without an entry point
```bash
docker run --rm -it --entrypoint "" ton-build bash
```
