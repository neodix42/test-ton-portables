#!/usr/bin/env bash

/app/test-portables.sh
if [ $? -ne 0 ]; then
  echo PORTABLE TESTS FAILED
  exit 1
else
  echo PORTABLE TESTS PASSED
  apt -h
  if [ $? -eq 0 ]; then
    if ! grep -q "Debian" /etc/os-release 2>/dev/null; then
    echo run ton deb packages testing on Ubuntu
    /app/test-deb.sh
    else
      echo Debian cant use Ubuntu repository
      exit 0
    fi
  else
    exit 0
  fi
fi

