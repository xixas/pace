#!/bin/sh
# Build the rpm inside a fedora container. Usage: build-rpm.sh SRC_DIR OUT_DIR
# SRC_DIR is a checkout (no VCS needed), OUT_DIR receives the .rpm.
set -eu
src=$1 out=$2
dnf -y -q install rpm-build make desktop-file-utils tar gzip >/dev/null
version=$(sed -n 's/^Version:[[:space:]]*//p' "$src/packaging/rpm/pace.spec")
top=$(mktemp -d)
mkdir -p "$top/SOURCES" "$top/pace-$version"
(cd "$src" && tar --exclude=.git --exclude=dist --exclude=__pycache__ -cf - .) | tar -xf - -C "$top/pace-$version"
tar -czf "$top/SOURCES/pace-$version.tar.gz" -C "$top" "pace-$version"
rpmbuild -bb --define "_topdir $top" "$src/packaging/rpm/pace.spec"
mkdir -p "$out"
cp "$top"/RPMS/*/*.rpm "$out"/
