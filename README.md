# Test TON artifacts
Set of Github actions used to test TON portable binaries, as well as deb packages from PPA launchpad repository against various Linux platforms.

Within every docker image we execute the following:

1. download portable binaries from https://github.com/neodix42/ton/releases/latest;
2. run tests against emulator tonlibjson using https://github.com/neodix42/test-ton-libs/releases/latest/download/test-ton-libs.jar utility;
3. run completely new standalone TON blockchain based on `downloaded` portable binaries. If 30 blocks get generated then we mark the test as successful;
4. on supported targets, install DEB packages from the TON Foundation PPA;
5. again run a new standalone TON blockchain using the installed PPA binaries. If 30 blocks are generated and the node processes exit without crashing, mark the test as successful.

DEB tests currently run on Ubuntu 22.04 (`jammy`) and 24.04 (`noble`), plus Linux Mint using either Ubuntu base, for `amd64` and `arm64`. Other targets explicitly report `DEB TESTS SKIPPED` and still run the portable tests. Extend the allowlist in `test-deb.sh` only after the PPA publishes `ton` for that release and architecture.

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

## Run a container without an entry point
```bash
docker run --rm -it --entrypoint "" ton-build bash
```
