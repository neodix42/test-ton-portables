#!/usr/bin/env bash
set -euo pipefail

# Keep portable tests on every platform, but only install published native DEBs.
. /etc/os-release
suite=${UBUNTU_CODENAME:-${VERSION_CODENAME:-}}
case "${ID:-}:$suite" in
  ubuntu:jammy|ubuntu:noble|linuxmint:jammy|linuxmint:noble) ;;
  *)
    echo "DEB TESTS SKIPPED: TON PPA is not supported on ${ID:-unknown}/$suite"
    exit 0
    ;;
esac
architecture=$(dpkg --print-architecture)
case "$architecture" in
  amd64|arm64) ;;
  *)
    echo "DEB TESTS SKIPPED: TON PPA is not supported on $suite/$architecture"
    exit 0
    ;;
esac

trap 'echo "DEB TESTS FAILED at line $LINENO: $BASH_COMMAND" >&2' ERR

# This suite also runs in fresh containers without a preceding portable test.
wget --timeout=30 --tries=3 -q -O /app/test-ton-libs.jar \
  https://github.com/neodix42/test-ton-libs/releases/latest/download/test-ton-libs.jar

# Use a repository-specific keyring; no keyserver or Launchpad API is needed.
install -d -m 0755 /etc/apt/keyrings
install -m 0644 /app/ton-foundation-ppa.asc /etc/apt/keyrings/ton-foundation-ppa.asc
printf 'deb [arch=%s signed-by=/etc/apt/keyrings/ton-foundation-ppa.asc] https://ppa.launchpadcontent.net/ton-foundation/ppa/ubuntu %s main\n' \
  "$architecture" "$suite" > /etc/apt/sources.list.d/ton-foundation-ppa.list

apt-get -o Acquire::Retries=3 -o APT::Update::Error-Mode=any update

# Remove portable artifacts before installing their package replacements.
rm -rf /usr/local/bin/*
rm -rf /usr/share/ton/smartcont/*
rm -rf /var/ton-work/*

DEBIAN_FRONTEND=noninteractive apt-get -o Acquire::Retries=3 install -y ton

cp /usr/share/data/gen-zerostate.fif /usr/share/ton/smartcont/
echo
if ! fift -V; then
  echo simple deb fift test FAILED
  exit 1
fi
validator-engine -V
validator-engine-console -V
lite-client -V
dht-server -V
echo
ldd /usr/lib/libtonlibjson.so.0.5
ldd /usr/lib/libemulator.so

echo testing libtonlibjson and libemulator...
if timeout --signal=TERM --kill-after=10s 180s java -jar /app/test-ton-libs.jar /usr/lib/libtonlibjson.so.0.5 /usr/lib/libemulator.so; then
  :
else
  status=$?
  if [ "$status" -eq 124 ]; then
    echo "DEB LIBRARY TESTS FAILED: timed out after 180 seconds" >&2
  else
    echo "DEB LIBRARY TESTS FAILED: status $status" >&2
  fi
  exit "$status"
fi
echo "DEB BINARY AND LIBRARY TESTS PASSED"

echo testing installed ton genesis binaries...
if TONLIBJSON_PATH=/usr/lib/libtonlibjson.so.0.5 LIBEMULATOR_PATH=/usr/lib/libemulator.so \
    timeout --signal=TERM --kill-after=30s 360s /scripts/start-node.sh; then
  :
else
  status=$?
  echo "DEB GENESIS TESTS FAILED (status $status; limit 360 seconds)" >&2
  exit "$status"
fi
echo "DEB GENESIS TESTS PASSED"
echo "DEB TESTS PASSED"
