#!/bin/sh
# Build the Arch package inside an archlinux (or cachyos) container. Usage: build-arch.sh SRC_DIR OUT_DIR
set -eu
src=$1 out=$2
pacman -Syu --noconfirm --needed base-devel make >/dev/null
version=$(sed -n 's/^Version:[[:space:]]*//p' "$src/packaging/rpm/pace.spec")
work=$(mktemp -d)
mkdir "$work/tree"
(cd "$src" && tar --exclude=.git --exclude=dist --exclude=__pycache__ -cf - .) | tar -xf - -C "$work/tree"
sed "s/^pkgver=.*/pkgver=$version/" "$src/packaging/arch/PKGBUILD" > "$work/PKGBUILD"
useradd -m builder 2>/dev/null || true
chown -R builder "$work"
su builder -c "cd '$work' && PKGDEST='$work' makepkg --nodeps --noconfirm" >/dev/null
mkdir -p "$out"
cp "$work"/pace-*.pkg.tar.zst "$out"/
