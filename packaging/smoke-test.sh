#!/bin/sh
# Install a built package in a clean container and check Pace starts. Usage: smoke-test.sh rpm|deb|arch PKG_DIR
set -eu
kind=$1 dir=$2
case $kind in
    rpm) dnf -y -q install "$dir"/*.rpm >/dev/null ;;
    deb) export DEBIAN_FRONTEND=noninteractive; apt-get update -qq; apt-get install -y -qq "$dir"/*.deb >/dev/null ;;
    arch) pacman -Syu --noconfirm >/dev/null; pacman -U --noconfirm "$dir"/*.pkg.tar.zst >/dev/null ;;
esac
export HOME=/tmp/pace-home XDG_CONFIG_HOME=/tmp/pace-home/c XDG_STATE_HOME=/tmp/pace-home/s
mkdir -p "$HOME"
set +e
paced --once
rc=$?
set -e
echo "paced --once exit=$rc (0 and a signed-out status expected: no session yet)"
[ "$rc" = 0 ]
grep -q '"state": "signed_out"' "$XDG_STATE_HOME/pace/status.json"
/usr/bin/python3 -c "import sys; sys.path.insert(0, '/usr/lib/pace'); import pace.engine; print('import pace.engine ok')"
/usr/bin/python3 -c "import gi
for n, v in (('Gtk', '4.0'), ('Adw', '1'), ('Secret', '1')):
    gi.require_version(n, v)
print('gi stack ok')"
/usr/bin/python3 -c "import sys; sys.path.insert(0, '/usr/lib/pace'); from pace._version import VERSION; print('version', VERSION); assert VERSION[0].isdigit()"
test -f /etc/xdg/autostart/io.github.xixas.Pace.daemon.desktop
test -f /usr/share/gnome-shell/extensions/pace@osmosys/metadata.json
echo "files ok"
case $kind in
    rpm) dnf -y -q remove pace >/dev/null ;;
    deb) apt-get remove -y -qq pace >/dev/null ;;
    arch) pacman -R --noconfirm pace >/dev/null ;;
esac
test ! -e /usr/bin/pace && test ! -e /usr/lib/pace && test ! -e /etc/xdg/autostart/io.github.xixas.Pace.daemon.desktop
echo "remove clean ok"
