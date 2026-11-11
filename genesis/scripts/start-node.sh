#!/usr/bin/env bash

GENESIS=${GENESIS:-"true"}
echo GENESIS=$GENESIS

if [ "$GENESIS" = "true" ]; then
  echo starting genesis...
  cp "${TONLIBJSON_PATH:-/usr/local/bin/libtonlibjson.so}" /usr/share/data/libtonlibjson.so || exit $?
  cp "${LIBEMULATOR_PATH:-/usr/local/bin/libemulator.so}" /usr/share/data/libemulator.so || exit $?
  /scripts/start-genesis.sh
else
  echo starting validator...
  if [ ! "$GENESIS_IP" ]; then
    echo No GENESIS_IP set, terminating...
    exit 1
  fi
  /scripts/start-validator.sh
fi
