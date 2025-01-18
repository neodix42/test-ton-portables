#!/usr/bin/env bash
pwd
uname -a
lsb_release -a
echo "Supported GLIBC on this server:"
strings /lib/x86_64-linux-gnu/libstdc++.so.6 | grep GLIBC

wget --no-check-certificate -q https://github.com/neodix42/test-ton-libs/releases/latest/download/test-ton-libs.jar
echo downloaded test-ton-libs

wget --no-check-certificate -q https://github.com/neodix42/ton/releases/latest/download/ton-linux-x86_64.zip
echo downloaded ton-appimages

unzip -qq ton-linux-x86_64.zip -d /usr/local/bin/
echo extracted ton-appimages
ls -lart /usr/local/bin/

mkdir -p /usr/share/ton /usr/lib/fift
cp -R /usr/local/bin/smartcont/* /usr/share/ton/smartcont/
cp -R /usr/local/bin/lib/* /usr/lib/fift/

cp /usr/share/data/gen-zerostate.fif /usr/share/ton/smartcont/
echo
fift -V
validator-engine -V
validator-engine-console -V
lite-client -V
dht-server -V
echo
ldd /usr/local/bin/libtonlibjson.so
ldd /usr/local/bin/libemulator.so

echo testing libtonlibjson and libemulator...
java -jar /app/test-ton-libs.jar /usr/local/bin/libtonlibjson.so /usr/local/bin/libemulator.so

echo testing other ton portable binaries...
/scripts/start-node.sh