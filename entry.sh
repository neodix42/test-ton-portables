#!/usr/bin/env bash

/app/test-portables.sh
if [ $? -ne 0 ]; then
  echo portable tests failed
else
  apt -h
  if [ $? -eq 0 ]; then
    echo run ton deb packages testing
    /app/test-deb.sh
  else
    exit 0
  fi
fi

