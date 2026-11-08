#!/bin/sh
# Build the deb inside an ubuntu/debian container. Usage: build-deb.sh SRC_DIR OUT_DIR
set -eu
src=$1 out=$2
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq build-essential debhelper make >/dev/null
work=$(mktemp -d)
(cd "$src" && tar --exclude=.git --exclude=dist --exclude=__pycache__ -cf - .) | tar -xf - -C "$work"
cp -r "$work/packaging/debian" "$work/debian"
(cd "$work" && dpkg-buildpackage -us -uc -b)
mkdir -p "$out"
cp "$work"/../pace_*_all.deb "$out"/
