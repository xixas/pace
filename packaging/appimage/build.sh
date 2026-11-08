#!/bin/sh
# Best-effort AppImage. Usage: build.sh SRC_DIR OUT_DIR VERSION
#
# Approach: the AppImage bundles only Pace (python package, extension, data). It does NOT bundle
# Python, GTK4, libadwaita or PyGObject: bundling those correctly (typelibs, gdk-pixbuf loaders,
# GSettings schemas, themes) is fragile. AppRun runs the HOST /usr/bin/python3 and needs the
# same host libraries as the rpm/deb (python3-gi, gtk4, libadwaita, libsecret). If they are
# missing AppRun prints which ones to install. The GNOME extension is not installed by an
# AppImage; AppRun copies it to ~/.local/share/gnome-shell/extensions on first run.
set -eu
src=$1 out=$2 version=${3:-0.0.0}
here=$(cd "$(dirname "$0")" && pwd)
work=$(mktemp -d)
appdir=$work/Pace.AppDir
make -C "$src" install DESTDIR="$appdir" PREFIX=/usr SYSCONFDIR=/etc LIBDIR=/usr/lib/pace
install -m755 "$here/AppRun" "$appdir/AppRun"
cp "$src/data/io.github.xixas.Pace.desktop" "$appdir/"
cp "$src/data/io.github.xixas.Pace.svg" "$appdir/"
cp "$src/data/io.github.xixas.Pace.svg" "$appdir/.DirIcon"

# Pinned release (not the moving "continuous" tag), verified before it is made executable.
# To bump: download the new release once, run sha256sum on it and update both lines.
AIT_VERSION=1.9.1
AIT_SHA256=ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0
curl -fsSL -o "$work/appimagetool" \
    "https://github.com/AppImage/appimagetool/releases/download/$AIT_VERSION/appimagetool-x86_64.AppImage"
echo "$AIT_SHA256  $work/appimagetool" | sha256sum -c -
chmod +x "$work/appimagetool"

mkdir -p "$out"
ARCH=x86_64 "$work/appimagetool" --appimage-extract-and-run "$appdir" "$out/Pace-$version-x86_64.AppImage"
