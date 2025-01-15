#!/usr/bin/env bash

wget --no-check-certificate -q https://github.com/neodix42/test-ton-libs/releases/latest/download/test-ton-libs.jar
echo downloaded test-ton-libs

wget --no-check-certificate -q https://github.com/neodix42/MyLocalTon/releases/download/v124/MyLocalTon-x86-64-dev.jar -o MyLocalTon-x86-64.jar
echo downloaded MyLocalTon

wget --no-check-certificate https://github.com/neodix42/ton/releases/latest/download/ton-linux-x86_64.zip -o ton-linux-x86_64.zip
echo downloaded ton-appimages