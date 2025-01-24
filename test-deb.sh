#!/usr/bin/env bash

#clean up previous ton portable binaries and ton genesis run
rm -rf /usr/local/bin/*
rm -rf /usr/share/ton/smartcont/*
rm -rf /var/ton-work/*

apt-key adv --keyserver keyserver.ubuntu.com --recv-keys F6A649124520E5F3
add-apt-repository -y ppa:ton-foundation/ppa
apt update -y
apt install -y ton

cp /usr/share/data/gen-zerostate.fif /usr/share/ton/smartcont/
echo
fift -V
validator-engine -V
validator-engine-console -V
lite-client -V
dht-server -V
echo
ldd /usr/lib/libtonlibjson.so.0.5
ldd /usr/lib/libemulator.so

echo testing libtonlibjson and libemulator...
java -jar /app/test-ton-libs.jar /usr/lib/libtonlibjson.so.0.5 /usr/lib/libemulator.so

echo testing other ton portable binaries...
/scripts/start-node.sh