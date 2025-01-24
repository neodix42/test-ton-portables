#!/usr/bin/env bash

#clean up previous ton portable binaries and ton genesis run
rm -rf /usr/local/bin/*
rm -rf /usr/share/ton/smartcont/*
rm -rf /var/ton-work/*

sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys F6A649124520E5F3
sudo add-apt-repository -y ppa:ton-foundation/ppa
sudo apt update -y
sudo apt install -y ton

#echo ARCH=$ARCH

#wget --no-check-certificate -q https://github.com/neodix42/test-ton-libs/releases/latest/download/test-ton-libs.jar
#echo downloaded test-ton-libs

#wget --no-check-certificate -q https://github.com/neodix42/ton/releases/latest/download/ton-linux-$ARCH.zip
#echo downloaded ton-appimages

#unzip -qq ton-linux-$ARCH.zip -d /usr/local/bin/
#echo extracted ton-appimages
#ls -lart /usr/local/bin/

#mkdir -p /usr/share/ton /usr/lib/fift
#cp -R /usr/local/bin/smartcont/* /usr/share/ton/smartcont/
#cp -R /usr/local/bin/lib/* /usr/lib/fift/

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
java -jar /app/test-ton-libs.jar/usr/lib/libtonlibjson.so.0.5 /usr/lib/libemulator.so

echo testing other ton portable binaries...
/scripts/start-node.sh