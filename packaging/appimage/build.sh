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
tool=${APPIMAGETOOL:-appimagetool}
if ! command -v "$tool" >/dev/null 2>&1; then
    curl -fsSL -o "$work/appimagetool" \
        https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x "$work/appimagetool"
    tool="$work/appimagetool --appimage-extract-and-run"
fi
mkdir -p "$out"
ARCH=x86_64 $tool "$appdir" "$out/Pace-$version-x86_64.AppImage"
