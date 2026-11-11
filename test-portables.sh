#!/usr/bin/env bash
echo ARCH=$ARCH
pwd
uname -a
lsb_release -a
echo "Supported GLIBC on this server:"
strings /lib/x86_64-linux-gnu/libstdc++.so.6 | grep GLIBC

wget --timeout=30 --tries=3 --waitretry=2 --no-check-certificate -q https://github.com/neodix42/test-ton-libs/releases/latest/download/test-ton-libs.jar || {
  echo "Failed to download the TON library tests" >&2
  exit 1
}
echo downloaded test-ton-libs

wget --timeout=30 --tries=3 --waitretry=2 --no-check-certificate -q https://github.com/neodix42/ton/releases/latest/download/ton-linux-$ARCH.zip || {
  echo "Failed to download TON portable binaries" >&2
  exit 1
}
echo downloaded ton-appimages

unzip -qq ton-linux-$ARCH.zip -d /usr/local/bin/
echo extracted ton-appimages
ls -lart /usr/local/bin/

mkdir -p /usr/share/ton /usr/lib/fift
cp -R /usr/local/bin/smartcont/* /usr/share/ton/smartcont/
cp -R /usr/local/bin/lib/* /usr/lib/fift/

cp /usr/share/data/gen-zerostate.fif /usr/share/ton/smartcont/
echo
fift -V
if [ $? -ne 0 ]; then
  echo simple portable fift test FAILED
  exit 1
fi
validator-engine -V
validator-engine-console -V
lite-client -V
dht-server -V
echo
ldd /usr/local/bin/libtonlibjson.so
ldd /usr/local/bin/libemulator.so

echo testing libtonlibjson and libemulator...
if timeout --signal=TERM --kill-after=10s 180s java -jar /app/test-ton-libs.jar /usr/local/bin/libtonlibjson.so /usr/local/bin/libemulator.so; then
  echo "Portable library tests PASSED"
else
  status=$?
  echo "Portable library tests FAILED (status $status; limit 180 seconds)" >&2
  exit "$status"
fi

echo testing other ton portable binaries...
if timeout --signal=TERM --kill-after=30s 360s /scripts/start-node.sh; then
  echo "Portable genesis tests PASSED"
else
  status=$?
  echo "Portable genesis tests FAILED (status $status; limit 360 seconds)" >&2
  exit "$status"
fi
echo "PORTABLE TESTS PASSED"
