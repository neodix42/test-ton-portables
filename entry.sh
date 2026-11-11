#!/usr/bin/env bash

if /app/test-portables.sh; then
  echo PORTABLE TESTS PASSED
else
  echo PORTABLE TESTS FAILED
  exit 1
fi

. /etc/os-release
case "${ID:-}" in
  ubuntu|linuxmint) exec /app/test-deb.sh ;;
  *) echo "DEB TESTS SKIPPED: TON PPA requires a supported Ubuntu-based distribution" ;;
esac

