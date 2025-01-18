#!/usr/bin/env bash
pwd
uname -a
lsb_release -a
echo "Supported GLIBC on this server:"
strings /lib/x86_64-linux-gnu/libstdc++.so.6 | grep GLIBC

wget --no-check-certificate -q https://github.com/neodix42/test-ton-libs/releases/latest/download/test-ton-libs.jar
echo downloaded test-ton-libs
#wget --no-check-certificate -q http://89.39.107.48:8000/MyLocalTon1.jar -O MyLocalTon.jar
#echo downloaded MyLocalTon
wget --no-check-certificate -q https://github.com/neodix42/ton/releases/latest/download/ton-linux-x86_64.zip
echo downloaded ton-appimages

unzip -qq ton-linux-x86_64.zip -d /usr/local/bin/
echo extracted ton-appimages
ls -lart /usr/local/bin/

mkdir -p /usr/share/ton /usr/lib/fift
cp -R /usr/local/bin/smartcont/* /usr/share/ton/smartcont/
cp -R /usr/local/bin/lib/* /usr/lib/fift/

cp /usr/share/data/gen-zerostate.fif /usr/share/ton/smartcont/

fift -V
validator-engine -V
validator-engine-console -V
lite-client -V
dht-server -V

ldd /usr/local/bin/libtonlibjson.so
ldd /usr/local/bin/libemulator.so

/scripts/start-node.sh