#!/usr/bin/env bash
pwd
uname -a
lsb_release -a
echo "Supported GLIBC on this server:"
strings /lib/x86_64-linux-gnu/libstdc++.so.6 | grep GLIBC

unzip -qq ton-linux-x86_64.zip -d bins

/app/bins/fift -V
/app/bins/validator-engine -V
/app/bins/validator-engine-console -V
/app/bins/lite-client -V
/app/bins/dht-server -V

ldd /app/bins/libtonlibjson.so
ldd /app/bins/libemulator.so

java -jar /app/test-ton-libs.jar /app/bins/libtonlibjson.so /app/bins/libemulator.so

java -jar /app/MyLocalTon-x86-64-dev.jar custom-binaries=/app/bins nogui debug